from __future__ import annotations

from dataclasses import dataclass

import jwt


@dataclass
class AuthCtx:
    user_id: str
    lab: dict | None
    role: str | None


def verify_token(token: str, jwt_secret: str) -> str:
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"],
                             audience="authenticated")
    except jwt.PyJWTError as e:
        raise ValueError(f"토큰 검증 실패: {e}") from None
    return payload["sub"]
