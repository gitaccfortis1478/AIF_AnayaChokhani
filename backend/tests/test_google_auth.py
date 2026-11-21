import pytest
from fastapi.testclient import TestClient

from formaos.api import main as api

ORIGIN = {"Origin": api.FRONTEND_ORIGINS[0]}


@pytest.fixture
def google_client(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setattr(api, "auth_store", api.FileAuthStore(tmp_path / "accounts.json"))
    with TestClient(api.app) as client:
        yield client


def claims_for(client, monkeypatch, **changes):
    config = client.get("/api/auth/google/config", headers=ORIGIN)
    assert config.status_code == 200
    assert config.headers["cache-control"] == "no-store"
    claims = {"sub": "google-123", "email": "user@gmail.com", "email_verified": True,
              "name": "Google User", "nonce": config.json()["nonce"]}
    claims.update(changes)
    def verify(token, transport, audience):
        assert audience == "test-client"
        return claims
    monkeypatch.setattr(api.id_token, "verify_oauth2_token", verify)
    return claims


def signin(client):
    return client.post("/api/auth/google", json={"credential": "google-token"}, headers=ORIGIN)


def test_google_account_returns_same_user_and_preserves_profile(google_client, monkeypatch):
    client = google_client
    claims_for(client, monkeypatch)
    first = signin(client)
    assert first.status_code == 200
    assert "httponly" in first.headers["set-cookie"].lower()
    user_id = first.json()["user"]["id"]
    assert client.get("/api/auth/me").json()["user"]["id"] == user_id
    assert signin(client).status_code == 401  # nonce consumed
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    claims_for(client, monkeypatch, email="changed@gmail.com")
    assert signin(client).json()["user"]["id"] == user_id
    assert len(api.auth_store._users) == 1
    assert "password_hash" not in api.auth_store.path.read_text()


@pytest.mark.parametrize("changes", [{"nonce": "wrong"}, {"email_verified": False}, {"sub": ""}, {"email": ""}])
def test_rejects_invalid_claims(google_client, monkeypatch, changes):
    claims_for(google_client, monkeypatch, **changes)
    assert signin(google_client).status_code == 401
    assert not api.auth_store._users


def test_rejects_invalid_signature_or_expired_token(google_client, monkeypatch):
    claims_for(google_client, monkeypatch)
    def reject(*args):
        raise ValueError("invalid signature, audience or expiry")
    monkeypatch.setattr(api.id_token, "verify_oauth2_token", reject)
    assert signin(google_client).status_code == 401


def test_requires_origin_nonce_and_configuration(google_client, monkeypatch):
    client = google_client
    assert client.get("/api/auth/google/config").status_code == 403
    assert client.post("/api/auth/google", json={"credential": "x"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert signin(client).status_code == 401
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    assert client.get("/api/auth/google/config", headers=ORIGIN).status_code == 503


def test_google_does_not_link_unverified_legacy_email(google_client, monkeypatch):
    legacy = api.auth_store.create_user("Legacy", "user@gmail.com", "old-password")
    claims_for(google_client, monkeypatch)
    result = signin(google_client)
    assert result.status_code == 200
    assert result.json()["user"]["id"] != legacy["id"]


def test_google_account_and_session_survive_reload(google_client, monkeypatch):
    claims = claims_for(google_client, monkeypatch)
    user = signin(google_client).json()["user"]
    token = google_client.cookies.get(api.AUTH_COOKIE_NAME)
    reloaded = api.FileAuthStore(api.auth_store.path)
    assert reloaded.user_for_token(token) == user
    assert reloaded.google_user(claims)["id"] == user["id"]


def test_production_cookies_and_google_outage(google_client, monkeypatch):
    monkeypatch.setenv("MYSPACE_COOKIE_SECURE", "1")
    monkeypatch.setenv("MYSPACE_COOKIE_SAMESITE", "none")
    response = google_client.get("/api/auth/google/config", headers=ORIGIN)
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=none" in cookie
    monkeypatch.setenv("MYSPACE_COOKIE_SECURE", "0")
    monkeypatch.setenv("MYSPACE_COOKIE_SAMESITE", "lax")
    claims_for(google_client, monkeypatch)
    def unavailable(*args):
        raise api.TransportError("Google unreachable")
    monkeypatch.setattr(api.id_token, "verify_oauth2_token", unavailable)
    assert signin(google_client).status_code == 503
