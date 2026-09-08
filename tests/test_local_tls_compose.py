from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_tls_gateway_terminates_https_without_exposing_application_dependencies():
    compose = yaml.safe_load((ROOT / "docker-compose.local-tls.yml").read_text(encoding="utf-8"))
    gateway = compose["services"]["tls-gateway"]

    assert gateway["depends_on"]["app"]["condition"] == "service_healthy"
    assert gateway["read_only"] is True
    assert "no-new-privileges:true" in gateway["security_opt"]
    assert gateway["volumes"] == [
        "./deploy/nginx/nexora-tls.conf:/etc/nginx/nginx.conf:ro",
        "${NEXORA_TLS_CERT_DIR:?Set NEXORA_TLS_CERT_DIR}:/etc/nginx/tls:ro",
    ]
    published_ports = " ".join(gateway["ports"])
    assert ":8080" in published_ports
    assert ":8443" in published_ports


def test_tls_gateway_enforces_modern_tls_redirect_and_proxy_headers():
    config = (ROOT / "deploy/nginx/nexora-tls.conf").read_text(encoding="utf-8")

    assert "ssl_protocols TLSv1.2 TLSv1.3;" in config
    assert 'return 308 https://$host$request_uri;' in config
    assert 'add_header Strict-Transport-Security "max-age=31536000" always;' in config
    assert "proxy_set_header X-Forwarded-Proto https;" in config
    assert "proxy_buffering off;" in config
    assert "ssl_certificate /etc/nginx/tls/fullchain.pem;" in config
    assert "ssl_certificate_key /etc/nginx/tls/privkey.pem;" in config
