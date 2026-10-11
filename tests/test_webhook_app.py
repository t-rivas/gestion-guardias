"""The publicly reachable delivery deployment has no app or proxy routes."""

import pytest
from fastapi.testclient import TestClient

from tests.test_private_access import event, signed_webhook


def delivery_client(neon, factory, monkeypatch):
    from app.main import app as full_app

    monkeypatch.setenv('AUTH_MODE', 'neon')
    monkeypatch.setenv('APP_BASE_URL', 'https://testserver')
    monkeypatch.setenv('NEON_AUTH_BASE_URL', 'https://ep-test.neonauth.us-east-1.aws.neon.tech/neondb/auth')
    monkeypatch.setenv('COOKIE_SECURE', 'true')
    from app.webhook import create_webhook_app

    app = create_webhook_app(full_app.state.auth_settings, factory)
    app.state.webhook_verifier = full_app.state.webhook_verifier
    app.state.email_sender = full_app.state.email_sender
    return TestClient(app, base_url='https://testserver')


def test_delivery_only_routes_and_signature_checks(neon, factory, monkeypatch):
    with delivery_client(neon, factory, monkeypatch) as client:
        for path in ('/', '/login', '/auth/callback?token=secret', '/personas', '/calendario/exportar/csv', '/health', '/docs', '/openapi.json', '/static/app.js', '/webhooks/neon-auth/'):
            for method in ('GET', 'POST'):
                response = client.request(method, path, follow_redirects=False)
                assert response.status_code == 404
                assert not response.headers.get('set-cookie')
                assert response.headers['cache-control'] == 'no-store'
        assert client.post('/webhooks/neon-auth', content=b'{}').status_code == 400
        assert client.post('/webhooks/neon-auth', content=b'x'*65537).status_code == 413
        assert not neon['sent']
        raw, headers = signed_webhook(neon, event())
        assert client.post('/webhooks/neon-auth', content=raw, headers=headers).status_code == 200
        assert client.post('/webhooks/neon-auth', content=raw, headers=headers).status_code == 200
        assert len(neon['sent']) == 1


@pytest.mark.parametrize('host,password,expected', [('smtp.gmail.com', 'abcd efgh ijkl mnop', 'abcdefghijklmnop'), ('mail.example.com', 'valid password with spaces', 'valid password with spaces')])
def test_sender_preserves_other_passwords(monkeypatch, host, password, expected):
    from app.services.auth_webhooks import send_email
    import smtplib
    calls = []
    class SMTP:
        def __init__(self, server, port, **kwargs):
            assert server == host and port == 465
            assert kwargs['context'].check_hostname
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def login(self, user, secret): calls.append((user, secret))
        def send_message(self, message):
            assert message['To'] == 'owner@example.com'
            assert 'https://app.example.com/auth/callback?token=test' in message.get_content()
    monkeypatch.setattr(smtplib, 'SMTP_SSL', SMTP)
    for key,value in {'SMTP_HOST':host,'SMTP_PORT':'465','SMTP_USERNAME':'sender@example.com','SMTP_PASSWORD':password,'SMTP_FROM':'sender@example.com','SMTP_SECURITY':'ssl'}.items():
        monkeypatch.setenv(key,value)
    send_email('owner@example.com', 'https://app.example.com/auth/callback?token=test')
    assert calls == [('sender@example.com', expected)]
