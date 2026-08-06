from __future__ import annotations

from dataclasses import dataclass

import jwt

# JWKS 클라이언트는 URL당 하나 — PyJWKClient가 키를 내부 캐시하므로 요청마다 원격 조회하지 않는다
_jwks_clients: dict[str, jwt.PyJWKClient] = {}


@dataclass
class AuthCtx:
    user_id: str
    lab: dict | None
    role: str | None


def verify_token(token: str, jwt_secret: str, jwks_url: str | None = None) -> str:
    # Supabase 신형 프로젝트는 토큰을 ES256(비대칭)으로 서명하고 공개 키를 JWKS로 배포한다.
    # 구형 프로젝트·테스트는 HS256 공유 비밀키. 헤더의 alg를 보고 검증 경로를 고른다 —
    # 단 alg별 키를 엄격히 분리해 alg 혼동 공격(공개 키를 HS256 비밀로 쓰기)을 차단한다.
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg == "HS256":
            key: object = jwt_secret
            algorithms = ["HS256"]
        elif alg in ("ES256", "RS256") and jwks_url:
            client = _jwks_clients.setdefault(jwks_url, jwt.PyJWKClient(jwks_url))
            key = client.get_signing_key_from_jwt(token).key
            algorithms = [alg]
        else:
            raise ValueError(f"지원하지 않는 토큰 서명 방식: {alg}")
        # iat 검사는 끈다 — 연구실 PC 시계는 서버와 수 초~수 분 어긋나는 게 보통이고,
        # 0.5초 차이로도 "not yet valid (iat)"가 난다. 만료(exp) 검사는 leeway 60초로 유지.
        payload = jwt.decode(token, key, algorithms=algorithms, audience="authenticated",
                             leeway=60, options={"verify_iat": False})
    except jwt.PyJWTError as e:
        raise ValueError(f"토큰 검증 실패: {e}") from None
    if not payload.get("sub"):
        raise ValueError("토큰에 sub(사용자 id)가 없습니다")
    return payload["sub"]
