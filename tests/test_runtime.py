import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.config_store import ConfigError
from app.frpc import FrpcManager


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        binary = root / 'frpc'
        binary.touch()
        self.manager = FrpcManager(binary, root / 'config.toml', root / 'log.txt', enabled=True)
        self.addCleanup(self.manager.close)

    def test_failed_verify_does_not_stop_existing_process(self):
        old = MagicMock()
        old.poll.return_value = None
        self.manager.process = old
        with patch('app.frpc.subprocess.run', return_value=SimpleNamespace(returncode=1)), patch('app.frpc.subprocess.Popen') as launch:
            with self.assertRaises(ConfigError) as error:
                self.manager.apply('new-revision')
            self.assertEqual(error.exception.status, 422)
            old.terminate.assert_not_called()
            launch.assert_not_called()

    def test_successful_apply_then_pending_and_exited_state(self):
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('frpc', 0.5), None]
        with patch('app.frpc.subprocess.run', return_value=SimpleNamespace(returncode=0)), patch('app.frpc.subprocess.Popen', return_value=process):
            self.assertEqual(self.manager.apply('revision-1')['apply_state'], 'applied')
            self.assertEqual(self.manager.status('revision-2')['apply_state'], 'pending')
            self.assertEqual(self.manager.status('revision-1')['apply_state'], 'applied')
            process.poll.return_value = 1
            self.assertFalse(self.manager.status('revision-1')['running'])
            self.assertEqual(self.manager.status('revision-1')['apply_state'], 'pending')

    def test_immediate_exit_is_not_reported_as_success(self):
        process = MagicMock()
        process.wait.return_value = 1
        process.poll.return_value = 1
        with patch('app.frpc.subprocess.run', return_value=SimpleNamespace(returncode=0)), patch('app.frpc.subprocess.Popen', return_value=process):
            with self.assertRaises(ConfigError) as error:
                self.manager.apply('revision')
            self.assertEqual(error.exception.status, 502)
            self.assertIsNone(self.manager.applied_revision)

    def test_runtime_starts_unknown_and_detects_saved_change(self):
        self.assertEqual(self.manager.status('original')['apply_state'], 'unknown')
        self.assertEqual(self.manager.status('saved')['apply_state'], 'pending')

    def test_verify_timeout_keeps_old_process(self):
        old = MagicMock()
        old.poll.return_value = None
        self.manager.process = old
        with patch('app.frpc.subprocess.run', side_effect=subprocess.TimeoutExpired('frpc', 15)):
            with self.assertRaises(ConfigError):
                self.manager.apply('revision')
        old.terminate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
