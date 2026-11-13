from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.healthcheck import check_http_health  # noqa: E402
from scripts.wg_audit import audit_mesh_config  # noqa: E402


class _HealthHandler(BaseHTTPRequestHandler):
    status_to_return = 200

    def do_GET(self) -> None:
        self.send_response(self.status_to_return)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args: object) -> None:
        return


class InfraBlueprintTests(unittest.TestCase):
    def test_sample_wireguard_mesh_config_passes_audit(self) -> None:
        sample = (REPO_ROOT / "wireguard" / "mesh-node.conf.example").read_text(encoding="utf-8")
        issues = audit_mesh_config(sample)
        self.assertEqual(issues, [])

    def test_wireguard_audit_rejects_default_route_in_mesh(self) -> None:
        unsafe = """
[Interface]
Address = 10.77.0.10/24

[Peer]
PublicKey = abc
AllowedIPs = 0.0.0.0/0
"""
        issues = audit_mesh_config(unsafe)
        self.assertTrue(any("default route" in item for item in issues))
        self.assertTrue(any("PersistentKeepalive" in item for item in issues))

    def test_http_healthcheck_success_and_fail_closed(self) -> None:
        server = HTTPServer(("127.0.0.1", 0), _HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/health"
            _HealthHandler.status_to_return = 200
            ok, code, detail = check_http_health(url)
            self.assertTrue(ok)
            self.assertEqual(code, 200)
            self.assertEqual(detail, "ok")

            _HealthHandler.status_to_return = 503
            ok, code, detail = check_http_health(url)
            self.assertFalse(ok)
            self.assertEqual(code, 503)
        finally:
            server.shutdown()
            server.server_close()

    def test_nginx_template_has_security_headers_and_healthz(self) -> None:
        nginx_conf = (REPO_ROOT / "nginx" / "conf.d" / "app.conf.template").read_text(encoding="utf-8")
        self.assertIn("Strict-Transport-Security", nginx_conf)
        self.assertIn("location = /healthz", nginx_conf)
        self.assertIn("limit_req zone=api_limit", nginx_conf)

    def test_atomic_release_and_rollback_on_posix(self) -> None:
        if os.name == "nt":
            self.skipTest("POSIX symlink rollback test runs on Linux/macOS CI runners")

        bash_bin = shutil.which("bash")
        self.assertIsNotNone(bash_bin)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            v1 = root / "releases" / "v1"
            v2 = root / "releases" / "v2"
            v1.mkdir(parents=True)
            v2.mkdir(parents=True)
            current = root / "current"
            script = REPO_ROOT / "deploy" / "atomic_release.sh"

            ok_res = subprocess.run(
                [str(bash_bin), str(script), str(v1), str(current), "true"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ok_res.returncode, 0, ok_res.stderr)
            self.assertEqual(os.readlink(current), str(v1))

            fail_res = subprocess.run(
                [str(bash_bin), str(script), str(v2), str(current), "false"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(fail_res.returncode, 0)
            self.assertEqual(os.readlink(current), str(v1))


if __name__ == "__main__":
    unittest.main()
