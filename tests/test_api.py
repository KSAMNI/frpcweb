import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import toml

from app import create_app
from app.config_store import ConfigError, ConfigStore


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'frpc.toml'
        self.meta = self.root / 'app_config.json'
        self.config.write_text('serverAddr = "example.com"\nserverPort = 7000\n[auth]\nmethod = "token"\ntoken = "test-secret-never-returned"\n', encoding='utf-8')
        self.meta.write_text(json.dumps({'target_ip': '127.0.0.1', 'custom': {'keep': True}}), encoding='utf-8')
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-key', 'FRPC_CONFIG': str(self.config),
                               'APP_CONFIG': str(self.meta), 'FRPC_LOG': str(self.root / 'frpc.log'),
                               'FRPC_MANAGE': False})
        self.client = self.app.test_client()
        self.store = self.app.extensions['config_store']

    def state(self):
        response = self.client.get('/api/state')
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def draft(self, **overrides):
        return {'name': 'nas', 'type': 'tcp', 'local_ip': '127.0.0.1', 'local_port': 80,
                'remote_port': 18080, 'display_name': '我的 NAS', 'visible': True,
                'favorite': False, 'group': '家庭服务', 'access_url': '', **overrides}

    def write(self, method, path, data, state=None):
        state = state or self.state()
        return self.client.open(path, method=method, json={**data, 'revision': state['revision']},
                                headers={'X-CSRF-Token': state['csrf_token']})

    def test_factory_does_not_start_process_or_write_configs(self):
        before = self.config.read_bytes(), self.meta.read_bytes()
        with patch('subprocess.Popen') as popen:
            self.state()
            popen.assert_not_called()
        self.assertEqual(before, (self.config.read_bytes(), self.meta.read_bytes()))

    def test_crud_rename_and_metadata(self):
        result = self.write('POST', '/api/proxies', self.draft())
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json['runtime']['apply_state'], 'pending')
        self.assertEqual(result.json['proxies'][0]['display_name'], '我的 NAS')
        result = self.write('PUT', '/api/proxies/nas', self.draft(name='nas-new', visible=False, favorite=True))
        self.assertEqual(result.status_code, 200)
        meta = json.loads(self.meta.read_text(encoding='utf-8'))
        self.assertNotIn('nas', meta['proxies_display'])
        self.assertEqual(meta['proxies_display']['nas-new']['favorite'], True)
        self.assertEqual(meta['custom'], {'keep': True})
        self.assertEqual(self.write('DELETE', '/api/proxies/nas-new', {}).status_code, 200)
        self.assertEqual(self.state()['proxies'], [])

    def test_unknown_fields_are_preserved_and_secrets_not_exposed(self):
        self.write('POST', '/api/proxies', self.draft())
        config = toml.load(self.config)
        config['proxies'][0]['transport'] = {'useEncryption': True}
        config['proxies'][0]['plugin'] = {'type': 'static_file', 'localPath': '/srv'}
        self.config.write_text(toml.dumps(config), encoding='utf-8')
        self.assertEqual(self.write('PUT', '/api/proxies/nas', self.draft(local_port=8080)).status_code, 200)
        saved = toml.load(self.config)
        self.assertTrue(saved['proxies'][0]['transport']['useEncryption'])
        self.assertEqual(saved['proxies'][0]['plugin']['localPath'], '/srv')
        self.assertEqual(saved['auth']['token'], 'test-secret-never-returned')
        self.assertNotIn('test-secret-never-returned', json.dumps(self.state()))

    def test_display_only_change_does_not_rewrite_frpc(self):
        self.write('POST', '/api/proxies', self.draft())
        before = self.config.read_bytes()
        result = self.write('PUT', '/api/proxies/nas', self.draft(display_name='新的名称', favorite=True))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(before, self.config.read_bytes())

    def test_bulk_groups_only_write_metadata_and_preserve_advanced_fields(self):
        self.write('POST', '/api/proxies', self.draft())
        self.write('POST', '/api/proxies', self.draft(name='ssh', local_port=22, remote_port=10022))
        config = toml.load(self.config)
        config['proxies'].append({'name': 'web-http', 'type': 'http', 'localPort': 8080,
                                  'customDomains': ['example.com'], 'transport': {'useEncryption': True}})
        self.config.write_text(toml.dumps(config) + '\n# keep this comment byte-for-byte\n', encoding='utf-8')
        meta = json.loads(self.meta.read_text(encoding='utf-8'))
        meta['proxies_display']['nas']['extra'] = {'keep': True}
        meta['proxies_display']['nas']['accessUrl'] = 'https://custom.example.com/path'
        self.meta.write_text(json.dumps(meta), encoding='utf-8')
        before = self.config.read_bytes()
        state = self.state()
        result = self.write('PUT', '/api/proxy-groups', {'names': ['nas', 'web-http', 'nas'], 'group': ' 新分组 '})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(result.json['frpc_revision'], state['frpc_revision'])
        rows = {row['name']: row for row in result.json['proxies']}
        self.assertEqual(rows['nas']['group'], '新分组')
        self.assertEqual(rows['web-http']['group'], '新分组')
        self.assertEqual(rows['ssh']['group'], '家庭服务')
        saved = json.loads(self.meta.read_text(encoding='utf-8'))
        self.assertEqual(saved['custom'], {'keep': True})
        self.assertEqual(saved['proxies_display']['nas']['extra'], {'keep': True})
        self.assertEqual(saved['proxies_display']['nas']['accessUrl'], 'https://custom.example.com/path')
        self.assertEqual(saved['proxies_display']['nas']['displayName'], '我的 NAS')
        result = self.write('PUT', '/api/proxy-groups', {'names': ['nas', 'web-http'], 'group': ''})
        self.assertEqual(result.status_code, 200)
        self.assertEqual([row['group'] for row in result.json['proxies'] if row['name'] != 'ssh'], ['', ''])
        with patch.object(self.store, '_write') as write:
            self.assertEqual(self.write('PUT', '/api/proxy-groups', {'names': ['nas'], 'group': ''}).status_code, 200)
            write.assert_not_called()

    def test_bulk_groups_validate_all_before_writing(self):
        self.write('POST', '/api/proxies', self.draft())
        before = self.config.read_bytes(), self.meta.read_bytes()
        for data in [{'names': [], 'group': ''}, {'names': 'nas', 'group': ''},
                     {'names': ['nas', 1], 'group': ''}, {'names': ['nas'], 'group': None},
                     {'names': ['nas'], 'group': 'x' * 51}, {'names': ['nas'], 'group': 'bad\nname'},
                     {'names': ['nas']}, {'names': [''], 'group': ''}]:
            with self.subTest(data=data):
                self.assertEqual(self.write('PUT', '/api/proxy-groups', data).status_code, 400)
                self.assertEqual((self.config.read_bytes(), self.meta.read_bytes()), before)
        result = self.write('PUT', '/api/proxy-groups', {'names': ['nas', 'missing'], 'group': '新分组'})
        self.assertEqual(result.status_code, 404)
        self.assertEqual((self.config.read_bytes(), self.meta.read_bytes()), before)

    def test_bulk_groups_require_fresh_revision_and_csrf(self):
        self.write('POST', '/api/proxies', self.draft())
        old = self.state()
        data = {'names': ['nas'], 'group': '新分组'}
        self.write('PUT', '/api/settings', {'target_ip': 'new.example.com'})
        before = self.meta.read_bytes()
        self.assertEqual(self.write('PUT', '/api/proxy-groups', data, old).status_code, 409)
        self.assertEqual(self.client.put('/api/proxy-groups', json=data).status_code, 403)
        current = self.state()
        response = self.client.put('/api/proxy-groups', json={**data, 'revision': current['revision']},
                                   headers={'X-CSRF-Token': current['csrf_token'], 'Origin': 'https://evil.test'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.meta.read_bytes(), before)

    def test_default_urls_remain_unset_when_host_or_port_changes(self):
        self.write('POST', '/api/proxies', self.draft())
        self.write('POST', '/api/proxies', self.draft(name='custom', remote_port=18081,
                                                    access_url='https://custom.example.com/path'))
        result = self.write('PUT', '/api/settings', {'target_ip': '2001:db8::1'})
        rows = {row['name']: row for row in result.json['proxies']}
        self.assertEqual(rows['nas']['access_url'], '')
        self.assertEqual(rows['custom']['access_url'], 'https://custom.example.com/path')
        result = self.write('PUT', '/api/proxies/nas', self.draft(remote_port=18082))
        self.assertEqual(result.json['proxies'][0]['access_url'], '')
        self.assertEqual(result.json['proxies'][0]['remote_port'], 18082)

    def test_validates_ports_hosts_names_urls_and_types(self):
        for override in [{'remote_port': 0}, {'local_port': 65536}, {'remote_port': True},
                         {'local_port': '80'}, {'local_ip': 'http://host:80'}, {'name': '../bad'},
                         {'name': ''}, {'type': 'http'}, {'visible': 'yes'},
                         {'access_url': 'javascript:alert(1)'}, {'access_url': 'https://user:pass@host/'},
                         {'access_url': 'https://host:99999/'}, {'access_url': 'http://host\\evil/'},
                         {'group': 'x' * 51}]:
            with self.subTest(override=override):
                response = self.write('POST', '/api/proxies', self.draft(**override))
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.json['fields'])
        self.assertEqual(self.state()['proxies'], [])

    def test_duplicates_are_rejected_but_tcp_udp_can_share_port(self):
        self.assertEqual(self.write('POST', '/api/proxies', self.draft()).status_code, 201)
        self.assertEqual(self.write('POST', '/api/proxies', self.draft()).status_code, 400)
        self.assertEqual(self.write('POST', '/api/proxies', self.draft(name='other')).status_code, 400)
        self.assertEqual(self.write('POST', '/api/proxies', self.draft(name='udp', type='udp')).status_code, 201)

    def test_stale_revision_never_overwrites(self):
        stale = self.state()
        self.write('POST', '/api/proxies', self.draft())
        before = self.config.read_bytes()
        result = self.write('POST', '/api/proxies', self.draft(name='stale', remote_port=18081), stale)
        self.assertEqual(result.status_code, 409)
        self.assertEqual(before, self.config.read_bytes())

    def test_csrf_cross_origin_and_legacy_get_delete(self):
        state = self.state()
        self.assertEqual(self.client.post('/api/proxies', json=self.draft()).status_code, 403)
        result = self.client.post('/api/proxies', json={**self.draft(), 'revision': state['revision']},
                                  headers={'X-CSRF-Token': state['csrf_token'], 'Origin': 'https://evil.test'})
        self.assertEqual(result.status_code, 403)
        self.assertEqual(self.client.get('/delete_proxy/nas').status_code, 404)
        self.assertEqual(self.client.get('/api/proxies/nas').status_code, 405)

    def test_bad_json_missing_proxy_and_unsupported_protocol(self):
        state = self.state()
        response = self.client.post('/api/proxies', json=[], headers={'X-CSRF-Token': state['csrf_token']})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.write('DELETE', '/api/proxies/missing', {}).status_code, 404)
        config = toml.load(self.config)
        config['proxies'] = [{'name': 'web', 'type': 'http', 'customDomains': ['test.example.com']}]
        self.config.write_text(toml.dumps(config), encoding='utf-8')
        self.assertFalse(self.state()['proxies'][0]['editable'])
        self.assertEqual(self.write('PUT', '/api/proxies/web', self.draft(name='web')).status_code, 400)

    def test_invalid_file_is_not_silently_overwritten(self):
        state = self.state()
        self.config.write_text('not valid TOML [[', encoding='utf-8')
        original = self.config.read_bytes()
        self.assertEqual(self.client.get('/api/state').status_code, 500)
        self.assertEqual(self.write('POST', '/api/proxies', self.draft(), state).status_code, 500)
        self.assertEqual(original, self.config.read_bytes())

    def test_settings_and_runtime_are_safe(self):
        config = self.config.read_bytes()
        self.assertEqual(self.write('PUT', '/api/settings', {'target_ip': 'https://bad/'}).status_code, 400)
        self.assertEqual(self.write('PUT', '/api/settings', {'target_ip': '::1'}).status_code, 200)
        self.assertEqual(self.state()['target_ip'], '::1')
        self.assertEqual(self.config.read_bytes(), config)
        with patch('subprocess.Popen') as process:
            self.assertEqual(self.write('POST', '/api/runtime/apply', {}).status_code, 403)
            process.assert_not_called()

    def test_logs_are_bounded_and_utf8_safe(self):
        log = self.root / 'frpc.log'
        log.write_bytes(b'old-data' * 20000 + '中文末尾'.encode())
        response = self.client.get('/api/logs')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['truncated'])
        self.assertTrue(response.json['log'].endswith('中文末尾'))
        self.assertLessEqual(len(response.json['log']), 32768)

    def test_second_file_write_failure_rolls_back(self):
        before = self.config.read_bytes(), self.meta.read_bytes()
        actual = self.store._write
        calls = 0
        def fail_second(path, content):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('disk failed')
            return actual(path, content)
        with patch.object(self.store, '_write', side_effect=fail_second):
            result = self.write('POST', '/api/proxies', self.draft())
        self.assertEqual(result.status_code, 500)
        self.assertEqual(before, (self.config.read_bytes(), self.meta.read_bytes()))

    def test_single_file_mount_fallback(self):
        import errno
        with patch('app.config_store.os.replace', side_effect=OSError(errno.EBUSY, 'mount point')):
            result = self.write('POST', '/api/proxies', self.draft())
        self.assertEqual(result.status_code, 201)
        self.assertEqual(toml.load(self.config)['proxies'][0]['name'], 'nas')
        self.assertEqual(list(self.root.glob('.frpc.toml.*')), [])
    def test_static_cache_and_api_no_store(self):
        dist = self.root / 'dist'
        (dist / 'assets').mkdir(parents=True)
        (dist / 'index.html').write_text('<html>console</html>', encoding='utf-8')
        (dist / 'assets' / 'test-hash.js').write_text('console.log("test");\n' * 500, encoding='utf-8')
        self.app.config['FRONTEND_DIST'] = str(dist)
        for path in ['/', '/config', '/settings', '/logs']:
            result = self.client.get(path)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.headers['Cache-Control'], 'no-store')
            result.close()
        result = self.client.get('/assets/test-hash.js', headers={'Accept-Encoding': 'gzip'})
        self.addCleanup(result.close)
        self.assertIn('immutable', result.headers['Cache-Control'])
        self.assertEqual(result.headers.get('Content-Encoding'), 'gzip')
        result.close()
        self.assertEqual(self.client.get('/api/state').headers['Cache-Control'], 'no-store')
        self.assertEqual(self.client.get('/assets/missing.js').status_code, 404)


if __name__ == '__main__':
    unittest.main()
