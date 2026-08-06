import jwt as pyjwt
import pytest

from horcrux.auth import verify_token

SECRET = "test-secret"


def make_token(sub="user-1", secret=SECRET, aud="authenticated", **extra):
    return pyjwt.encode({"sub": sub, "aud": aud, **extra}, secret, algorithm="HS256")


def test_verify_token_returns_user_id():
    assert verify_token(make_token(), SECRET) == "user-1"


def test_verify_token_rejects_bad_signature():
    with pytest.raises(ValueError):
        verify_token(make_token(secret="wrong"), SECRET)


def test_verify_token_rejects_expired():
    tok = make_token(exp=0)
    with pytest.raises(ValueError):
        verify_token(tok, SECRET)


def test_verify_token_es256_via_jwks(monkeypatch):
    # 신형 Supabase: ES256 서명 + JWKS 공개 키. 원격 조회는 모킹한다.
    from cryptography.hazmat.primitives.asymmetric import ec

    from horcrux import auth as auth_mod

    priv = ec.generate_private_key(ec.SECP256R1())
    tok = pyjwt.encode({"sub": "user-9", "aud": "authenticated"}, priv, algorithm="ES256")

    class FakeKey:
        key = priv.public_key()

    class FakeJWKClient:
        def __init__(self, url): pass
        def get_signing_key_from_jwt(self, token): return FakeKey()

    monkeypatch.setattr(auth_mod.jwt, "PyJWKClient", FakeJWKClient)
    auth_mod._jwks_clients.clear()
    assert verify_token(tok, SECRET, "https://x.supabase.co/auth/v1/.well-known/jwks.json") == "user-9"


def test_verify_token_es256_without_jwks_url_fails():
    from cryptography.hazmat.primitives.asymmetric import ec
    priv = ec.generate_private_key(ec.SECP256R1())
    tok = pyjwt.encode({"sub": "u", "aud": "authenticated"}, priv, algorithm="ES256")
    with pytest.raises(ValueError):
        verify_token(tok, SECRET)   # JWKS 없으면 거부 — 비밀키로 대충 검증하지 않는다
