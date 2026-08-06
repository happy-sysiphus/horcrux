import pytest
from cryptography.fernet import Fernet

from horcrux import labs as labs_mod
from horcrux.labs import LabsDB, new_invite_code


class FakeTable:
    def __init__(self, store, name):
        self.store, self.name = store, name
        self._filters, self._payload, self._op = {}, None, None

    def insert(self, row):  self._op, self._payload = "insert", row; return self
    def update(self, row):  self._op, self._payload = "update", row; return self
    def upsert(self, row):  self._op, self._payload = "upsert", row; return self
    def select(self, *_):   self._op = self._op or "select"; return self
    def eq(self, k, v):     self._filters[k] = v; return self

    def execute(self):
        rows = self.store.setdefault(self.name, [])
        if self._op == "insert":
            row = dict(self._payload)
            if self.name == "labs":  # real schema: id uuid default gen_random_uuid()
                row.setdefault("id", f"{self.name}-{len(rows) + 1}")
            rows.append(row)
            return type("R", (), {"data": [rows[-1]]})
        matched = [r for r in rows if all(r.get(k) == v for k, v in self._filters.items())]
        if self._op == "update":
            for r in matched: r.update(self._payload)
        if self._op == "upsert":
            # 실제 postgres on-conflict와 동일하게 PK로 매칭 (llm_usage PK = lab_id+day)
            pk = ("lab_id", "day")
            matched = [r for r in rows if all(r.get(k) == self._payload[k] for k in pk)]
            if matched: matched[0].update(self._payload)
            else: rows.append(dict(self._payload)); matched = [rows[-1]]
        return type("R", (), {"data": matched})


class FakeClient:
    def __init__(self):
        self.store = {}
    def table(self, name):
        return FakeTable(self.store, name)


@pytest.fixture
def db(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(labs_mod, "create_client", lambda url, key: fake)
    d = LabsDB("http://x", "svc", Fernet.generate_key().decode())
    d._fake = fake
    return d


def test_create_lab_registers_admin(db):
    lab = db.create_lab("user-1", "산화막랩")
    assert len(lab["invite_code"]) == 8
    assert db.lab_for_user("user-1") == (lab, "admin")


def test_join_lab_by_code_and_bad_code(db):
    lab = db.create_lab("user-1", "랩")
    db.join_lab("user-2", lab["invite_code"])
    assert db.lab_for_user("user-2")[1] == "member"
    with pytest.raises(LookupError):
        db.join_lab("user-3", "nope0000")


def test_credential_roundtrip_encrypted(db):
    lab = db.create_lab("u", "랩")
    db.set_credential(lab["id"], "claude", "secret-token")
    stored = db._fake.store["labs"][0]["llm_credential"]
    assert "secret-token" not in stored           # 평문 저장 금지
    assert db.get_credential(lab["id"]) == ("claude", "secret-token")


def test_bump_usage_enforces_limit(db):
    lab = db.create_lab("u", "랩")
    other = db.create_lab("u2", "다른 랩")
    assert db.bump_usage(lab["id"], limit=2) is True
    assert db.bump_usage(lab["id"], limit=2) is True
    assert db.bump_usage(lab["id"], limit=2) is False   # 3회째 = 초과
    # 카운터는 연구실별로 독립 — 한 랩이 소진해도 다른 랩은 영향 없음
    assert db.bump_usage(other["id"], limit=2) is True
    assert db.bump_usage(lab["id"], limit=2) is False
