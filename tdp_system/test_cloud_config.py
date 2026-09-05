"""Cloud variables take precedence without leaking or reviving file secrets."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from .msmi_client import MsmiConfig, MsmiError
from .minvoice_client import MinvoiceConfig, MinvoiceError


class ConnectorEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_cloud_only_credentials(self):
        with patch.dict(os.environ, MSMI_API_BASE_URL='https://msmi.test/', MSMI_API_TOKEN='token',
                        MINVOICE_API_BASE_URL='https://invoice.test/', MINVOICE_USERNAME='user',
                        MINVOICE_PASSWORD='password', MINVOICE_UNIT_CODE='HN'):
            self.assertEqual(MsmiConfig.from_env_files([]), MsmiConfig('https://msmi.test', 'token'))
            self.assertEqual(MinvoiceConfig.from_env_files([]),
                             MinvoiceConfig('https://invoice.test', 'user', 'password', 'HN'))

    def test_environment_overrides_file_and_empty_does_not_revive_secret(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / '.env'
            file.write_text('MSMI_API_BASE_URL=https://old.test\nMSMI_API_TOKEN=old\n'
                            'MINVOICE_API_BASE_URL=https://old.test\nMINVOICE_USERNAME=old\n'
                            'MINVOICE_PASSWORD=old\n', encoding='utf-8')
            self.assertEqual(MsmiConfig.from_env_files([file]).api_token, 'old')
            self.assertEqual(MinvoiceConfig.from_env_files([file]).username, 'old')
            with patch.dict(os.environ, MSMI_API_TOKEN='new', MINVOICE_PASSWORD='new'):
                self.assertEqual(MsmiConfig.from_env_files([file]).api_token, 'new')
                self.assertEqual(MinvoiceConfig.from_env_files([file]).password, 'new')
            with patch.dict(os.environ, MSMI_API_TOKEN='', MINVOICE_PASSWORD=''):
                with self.assertRaises(MsmiError): MsmiConfig.from_env_files([file])
                with self.assertRaises(MinvoiceError): MinvoiceConfig.from_env_files([file])

    def test_hosted_start_preserves_print_template_and_skips_catalog_reimport(self):
        from . import server, cloud_server
        from . import cloud_auth
        with tempfile.TemporaryDirectory() as root:
            database = Path(root) / 'existing.sqlite3'
            database.write_bytes(b'existing database')
            template = server.MASTER_SOURCE
            stop, worker = Mock(), Mock()
            with patch.dict(os.environ, TDP_DATA_DIR=root, TDP_DB_PATH=str(database)), \
                    patch.object(cloud_auth, 'install_cloud_auth'), \
                    patch.object(server, 'init_database') as init, \
                    patch.object(server, 'start_backup_worker', return_value=(stop, worker)), \
                    patch('waitress.serve'):
                cloud_server.main()
            init.assert_called_once_with(sync_master=False)
            self.assertEqual(server.MASTER_SOURCE, template)
            stop.set.assert_called_once()


if __name__ == '__main__':
    unittest.main()
