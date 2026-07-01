import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROXY = ROOT / "deploy" / "reverse-proxy"


class ReverseProxyExampleTests(unittest.TestCase):
    def test_nginx_example_covers_required_proxy_controls(self):
        text = (PROXY / "nginx-junas.conf").read_text(encoding="utf-8")

        for token in (
            "listen 443 ssl http2",
            "ssl_certificate",
            "ssl_protocols TLSv1.2 TLSv1.3",
            "client_max_body_size 25m",
            "proxy_connect_timeout 5s",
            "proxy_read_timeout 30s",
            "proxy_send_timeout 30s",
            "log_format junas_no_body",
            "access_log /var/log/nginx/junas_access.log junas_no_body",
            "location = /metrics",
            "allow 10.0.0.0/8",
            "deny all",
            "location ~ ^/(review|classify|classify/batch|safe-rewrite",
            "location ~ ^/review/[^/]+(/decision)?$",
            "location ^~ /local/",
            "return 404",
        ):
            self.assertIn(token, text)
        self.assertNotIn("$request_body", text)
        self.assertNotIn("$http_authorization", text)

    def test_reverse_proxy_docs_are_linked_from_deployment_hardening(self):
        readme = (PROXY / "README.md").read_text(encoding="utf-8")
        docs = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")

        self.assertIn("nginx-junas.conf", readme)
        self.assertIn("deploy/reverse-proxy/nginx-junas.conf", docs)


if __name__ == "__main__":
    unittest.main()
