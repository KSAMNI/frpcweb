"""Isolated browser-test server; real project configuration is never accessed."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import toml
from app import create_app
from waitress import serve


def seed(directory):
    rows = [
        ('nas-web', '我的 NAS', '家庭服务', 'tcp', 5000, 15000, 'http://127.0.0.1:15000', True),
        ('jellyfin', '影音中心', '家庭服务', 'tcp', 8096, 18096, 'http://127.0.0.1:18096', True),
        ('home-assistant', '智能家居', '家庭服务', 'tcp', 8123, 18123, 'http://127.0.0.1:18123', False),
        ('gitea', '代码仓库', '开发工具', 'tcp', 3000, 13000, 'https://git.example.com', False),
        ('ssh-server', '开发服务器', '开发工具', 'tcp', 22, 10022, '', False),
        ('game-udp', '游戏服务器', '其他服务', 'udp', 27015, 27015, '', False),
    ]
    config = {'serverAddr': '127.0.0.1', 'serverPort': 7000, 'proxies': []}
    meta = {'target_ip': '192.168.1.10', 'proxies_display': {}}
    for name, label, group, protocol, local, remote, url, favorite in rows:
        config['proxies'].append({'name': name, 'type': protocol, 'localIP': '127.0.0.1', 'localPort': local, 'remotePort': remote})
        meta['proxies_display'][name] = {'displayName': label, 'visible': True, 'group': group, 'favorite': favorite, 'accessUrl': url}
    (directory / 'frpc.toml').write_text(toml.dumps(config), encoding='utf-8')
    (directory / 'app_config.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
    (directory / 'frpc.log').write_text('2026-10-08 [I] fixture log only; no FRPC process is running\n', encoding='utf-8')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='frpc-ui-e2e-') as temp:
        directory = Path(temp)
        seed(directory)
        app = create_app({'TESTING': True, 'FRPC_CONFIG': str(directory / 'frpc.toml'),
                          'APP_CONFIG': str(directory / 'app_config.json'), 'FRPC_LOG': str(directory / 'frpc.log'),
                          'FRPC_MANAGE': False})
        @app.post('/__test/reset')
        def reset():
            with app.extensions['config_store'].lock:
                seed(directory)
            return {'ok': True}
        serve(app, host='127.0.0.1', port=int(os.environ.get('E2E_PORT', '18080')))
