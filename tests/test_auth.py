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
