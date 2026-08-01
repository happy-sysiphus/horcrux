import pytest
from fastapi.testclient import TestClient

from horcrux import server
from horcrux.config import Config
from horcrux.ingest import ParsedLog
from horcrux.records import ExperimentRecord, record_path, save_record


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "run_absorb", lambda cfg: 0)
    return TestClient(server.create_app(Config(vault=tmp_path))), tmp_path


def test_parse_returns_parsed_and_gaps(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(server, "parse_log",
                        lambda cfg, text, vcfg: ParsedLog(objective="막 증착"))
    r = c.post("/api/parse", json={"text": "오늘 증착"})
    assert r.status_code == 200
    assert r.json()["parsed"]["objective"] == "막 증착"
    assert any("결과" in g for g in r.json()["gaps"])  # results 미기재 → 재질문


def test_save_creates_record_with_followup(client):
    c, vault = client
    parsed = ParsedLog(experiment_type="증착", objective="o", results="r",
                       summary="요약").model_dump()
    r = c.post("/api/records", json={"text": "원문", "parsed": parsed,
                                     "followup_of": "2026-07-31_x-001"})
    assert r.status_code == 200
    rid = r.json()["id"]
    assert record_path(vault, rid).exists()
    detail = c.get(f"/api/records/{rid}").json()
    assert detail["record"]["followup_of"] == "2026-07-31_x-001"
    assert "원문" in detail["body"]


def test_save_raw_needs_review(client):
    c, _ = client
    r = c.post("/api/records/raw", json={"text": "깨진 로그"})
    rid = r.json()["id"]
    detail = c.get(f"/api/records/{rid}").json()
    assert detail["record"]["needs_review"] is True


def test_ask_passthrough(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(server, "diagnose_data", lambda cfg, t: {
        "answer": "a", "evidence": "none", "records": [], "wiki": []})
    assert c.post("/api/ask", json={"text": "q"}).json()["evidence"] == "none"


def test_list_and_detail_404(client):
    c, vault = client
    save_record(vault, ExperimentRecord(id="2026-08-01_a-001", date="2026-08-01"), "원문", "s")
    assert c.get("/api/records").json()["records"][0]["id"] == "2026-08-01_a-001"
    assert c.get("/api/records/없는-id").status_code == 404


def test_feedback_updates_resolution(client):
    c, vault = client
    save_record(vault, ExperimentRecord(id="2026-08-01_b-001", date="2026-08-01"), "원문", "s")
    r = c.post("/api/feedback", json={"record_id": "2026-08-01_b-001",
                                      "resolved": True, "cause": "타겟 산화"})
    assert r.status_code == 200
    detail = c.get("/api/records/2026-08-01_b-001").json()
    assert detail["record"]["resolution"]["resolved"] is True
    assert detail["record"]["resolution"]["actual_cause"] == "타겟 산화"


def test_config_endpoint(client):
    c, _ = client
    j = c.get("/api/config").json()
    assert "objective" in j["required_fields"]
    assert j["provider"] == "claude"
