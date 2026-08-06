from __future__ import annotations

import datetime
import secrets

from cryptography.fernet import Fernet

try:
    from supabase import create_client
except ImportError:      # deploy extra 미설치 로컬 — LabsDB 생성 시점에만 필요
    # ModuleNotFoundError가 아니라 ImportError를 잡는 이유: 저장소 루트의 supabase/
    # (schema.sql 보관용) 디렉터리가 네임스페이스 패키지로 잡혀 실제 supabase 패키지가
    # 없을 때 "cannot import name 'create_client'" ImportError가 발생하기 때문.
    create_client = None


def new_invite_code() -> str:
    return secrets.token_hex(4)


class LabsDB:
    def __init__(self, url: str, service_key: str, fernet_key: str):
        self._c = create_client(url, service_key)
        self._fernet = Fernet(fernet_key.encode())

    def create_lab(self, user_id: str, name: str) -> dict:
        row = {"name": name, "invite_code": new_invite_code(), "created_by": user_id}
        lab = self._c.table("labs").insert(row).execute().data[0]
        self._c.table("lab_members").insert(
            {"lab_id": lab["id"], "user_id": user_id, "role": "admin"}).execute()
        return lab

    def join_lab(self, user_id: str, invite_code: str) -> dict:
        found = self._c.table("labs").select("*").eq("invite_code", invite_code).execute().data
        if not found:
            raise LookupError("초대 코드가 올바르지 않습니다")
        lab = found[0]
        self._c.table("lab_members").insert(
            {"lab_id": lab["id"], "user_id": user_id, "role": "member"}).execute()
        return lab

    def lab_for_user(self, user_id: str) -> tuple[dict, str] | None:
        ms = self._c.table("lab_members").select("*").eq("user_id", user_id).execute().data
        if not ms:
            return None
        labs = self._c.table("labs").select("*").eq("id", ms[0]["lab_id"]).execute().data
        return labs[0], ms[0]["role"]

    def update_settings(self, lab_id: str, fields: dict) -> None:
        self._c.table("labs").update(fields).eq("id", lab_id).execute()

    def set_credential(self, lab_id: str, provider: str, secret: str) -> None:
        enc = self._fernet.encrypt(secret.encode()).decode()
        self.update_settings(lab_id, {"llm_mode": "own", "llm_provider": provider,
                                      "llm_credential": enc})

    def get_credential(self, lab_id: str) -> tuple[str, str] | None:
        labs = self._c.table("labs").select("*").eq("id", lab_id).execute().data
        if not labs or not labs[0].get("llm_credential"):
            return None
        return labs[0]["llm_provider"], self._fernet.decrypt(
            labs[0]["llm_credential"].encode()).decode()

    # ponytail: read-then-write라 동시 요청에 근사 카운트 — 정확 카운트 필요하면 postgres rpc increment로 교체
    def bump_usage(self, lab_id: str, limit: int) -> bool:
        day = datetime.date.today().isoformat()
        rows = (self._c.table("llm_usage").select("*")
                .eq("lab_id", lab_id).eq("day", day).execute().data)
        count = (rows[0]["count"] if rows else 0) + 1
        if count > limit:
            return False
        self._c.table("llm_usage").upsert(
            {"lab_id": lab_id, "day": day, "count": count}).execute()
        return True
