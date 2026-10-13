"""FUT-02: no-Django local/LAN preflight and fail-closed TLS regression."""
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

import check_deployment_profile as check

BASE = {"DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1,api",
        "AI_COMPASS_PROFILE": "development"}


class DeploymentTests(unittest.TestCase):
    def test_loopback_development_is_usable_without_external_secrets(self):
        cfg = check.preflight(BASE, Path("."))
        self.assertFalse(cfg["secure"])
        self.assertIsNone(cfg["proxy_header"])

    def test_dev_cannot_silently_listen_on_public_or_lan(self):
        for overrides in ({"DJANGO_ALLOWED_HOSTS": "0.0.0.0,api"},
                          {"DJANGO_ALLOWED_HOSTS": "192.168.1.20,api"},
                          {"AI_COMPASS_LAN_BIND": "192.168.1.20"},
                          {"AI_COMPASS_TLS_PROXY": "1"},
                          {"DJANGO_CSRF_TRUSTED_ORIGINS": "http://lan.local"}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(check.module.ProfileError):
                    check.preflight(dict(BASE, **overrides), Path("."))

    def lan(self):
        return {"AI_COMPASS_PROFILE": "lan", "AI_COMPASS_TLS_PROXY": "1",
                "AI_COMPASS_LAN_BIND": "192.168.1.20",
                "DJANGO_SECRET_KEY": "s" * 48, "DB_PASSWORD": "p" * 48,
                "DJANGO_ALLOWED_HOSTS": "api,localhost,127.0.0.1,192.168.1.20,host.lan",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://192.168.1.20,https://host.lan"}

    def test_lan_requires_private_bind_tls_and_explicit_trusted_origins(self):
        for overrides in ({"AI_COMPASS_LAN_BIND": "0.0.0.0"},
                          {"AI_COMPASS_LAN_BIND": "8.8.8.8"},
                          {"AI_COMPASS_LAN_BIND": "127.0.0.1"},
                          {"AI_COMPASS_TLS_PROXY": "0"},
                          {"DJANGO_SECRET_KEY": "test"},
                          {"DB_PASSWORD": "REPLACE_WITH_RANDOM_PASSWORD"},
                          {"DJANGO_ALLOWED_HOSTS": "*.lan"},
                          {"DJANGO_ALLOWED_HOSTS": "8.8.8.8,192.168.1.20"},
                          {"DJANGO_CSRF_TRUSTED_ORIGINS": "http://192.168.1.20"},
                          {"DJANGO_CSRF_TRUSTED_ORIGINS": "https://evil.example"},
                          {"DJANGO_CSRF_TRUSTED_ORIGINS": "https://host.lan"},
                          {"DJANGO_CSRF_TRUSTED_ORIGINS": "https://192.168.1.20:8443"}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(check.module.ProfileError):
                    check.preflight(dict(self.lan(), **overrides), Path("."))

    def test_lan_validates_actual_certificate_paths_permissions_and_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            cert = base / "lan.crt"
            key = base / "lan.key"
            cert.write_text("invalid-certificate")
            key.write_text("invalid-private-key")
            key.chmod(0o600)
            env = dict(self.lan(), AI_COMPASS_LAN_CERT=str(cert), AI_COMPASS_LAN_KEY=str(key))
            with self.assertRaises(Exception):
                check.preflight(env, base)  # invalid chain fails; no trusted TLS asserted
            with patch.object(check.ssl.SSLContext, "load_cert_chain") as verify:
                cfg = check.preflight(env, base)
                self.assertTrue(cfg["secure"])
                self.assertEqual(cfg["proxy_header"], ("HTTP_X_FORWARDED_PROTO", "https"))
                verify.assert_called_once_with(str(cert), str(key))
            key.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "group/other"):
                check.preflight(env, base)
            key.chmod(0o600)
            with self.assertRaisesRegex(ValueError, "certificate"):
                check.preflight({k: v for k, v in env.items() if k != "AI_COMPASS_LAN_CERT"}, base)

    def test_env_parser_reads_literal_credentials_without_executing_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / ".env"
            p.write_text("AI_COMPASS_PROFILE=development\nDJANGO_ALLOWED_HOSTS=api,localhost\n")
            self.assertEqual(check.read_env(p)["AI_COMPASS_PROFILE"], "development")
            self.assertEqual(check.preflight(check.read_env(p), p.parent)["profile"], "development")

    def internet(self):
        return {"AI_COMPASS_PROFILE": "internet", "AI_COMPASS_TLS_PROXY": "1",
                "DJANGO_SECRET_KEY": "k" * 40, "DB_PASSWORD": "p" * 40,
                "DJANGO_ALLOWED_HOSTS": "compass.example.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://compass.example.com"}

    def test_internet_profile_requires_tls_certificate_paths_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with self.assertRaisesRegex(ValueError, "Internet"):
                check.preflight(self.internet(), base)  # no certificate supplied
            key = base / "i.key"
            key.write_text("key")
            key.chmod(0o600)
            cert = base / "i.crt"
            cert.write_text("cert")
            env = dict(self.internet(), AI_COMPASS_LAN_CERT=str(cert),
                       AI_COMPASS_LAN_KEY=str(key))
            with patch.object(check.ssl.SSLContext, "load_cert_chain") as verify:
                cfg = check.preflight(env, base)
                self.assertEqual(cfg["profile"], "internet")
                self.assertTrue(cfg["secure"])
                self.assertEqual(cfg["hsts_seconds"], 600)
                verify.assert_called_once_with(str(cert), str(key))
            key.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "group/other"):
                check.preflight(env, base)

    def test_internet_profile_refuses_cleartext_and_internal_hosts(self):
        for overrides in ({"AI_COMPASS_TLS_PROXY": "0"},
                          {"DJANGO_ALLOWED_HOSTS": "localhost"},
                          {"DJANGO_ALLOWED_HOSTS": "192.168.1.5"},
                          {"DJANGO_CSRF_TRUSTED_ORIGINS": "http://compass.example.com"},
                          {"DJANGO_SECRET_KEY": "REPLACE_WITH_RANDOM_SECRET"}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(check.module.ProfileError):
                    check.module.configuration(dict(self.internet(), **overrides))


if __name__ == "__main__":
    unittest.main()
