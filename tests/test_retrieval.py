from horcrux import retrieval as rt
from horcrux.config import Config
from horcrux.records import ExperimentRecord, Resolution, Symptom, save_record


def make_vault(tmp_path, n=3):
    for i in range(n):
        rec = ExperimentRecord(
            id=f"2026-07-19_exp-{i:03d}", date="2026-07-19", experiment_type="스퍼터 증착",
            equipment=["RF 스퍼터"], symptom=Symptom(category="low_value", description="낮음"),
        )
        save_record(tmp_path, rec, f"원문 {i}", f"정리 {i}")
    return tmp_path


def test_retrieve_selects_records_and_filters_hallucinations(tmp_path, monkeypatch):
    make_vault(tmp_path, 3)
    captured = {}

    def fake_parsed(cfg, system, user, schema):
        captured["user"] = user
        return rt.Selected(record_ids=["2026-07-19_exp-001", "없는-id"])

    monkeypatch.setattr(rt, "generate_parsed", fake_parsed)
    res = rt.retrieve(Config(vault=tmp_path), "증착률 낮음")
    assert [r["id"] for r in res["records"]] == ["2026-07-19_exp-001"]  # 카탈로그에 없는 id는 무시
    assert res["wiki"] == []
    assert "2026-07-19_exp-000" in captured["user"]  # 전체 레코드가 카탈로그에 포함


def test_retrieve_includes_wiki_articles(tmp_path, monkeypatch):
    make_vault(tmp_path, 1)
    art_dir = tmp_path / "wiki" / "equipment"
    art_dir.mkdir(parents=True)
    (art_dir / "rf-스퍼터.md").write_text("---\nname: RF 스퍼터\n---\n\n본문", encoding="utf-8")

    def fake_parsed(cfg, system, user, schema):
        assert "equipment/rf-스퍼터" in user  # 위키 목록이 카탈로그에 포함
        return rt.Selected(wiki_ids=["equipment/rf-스퍼터", "없는/아티클"])

    monkeypatch.setattr(rt, "generate_parsed", fake_parsed)
    res = rt.retrieve(Config(vault=tmp_path), "질의")
    assert [w["id"] for w in res["wiki"]] == ["equipment/rf-스퍼터"]


def test_retrieve_respects_top_k(tmp_path, monkeypatch):
    make_vault(tmp_path, 3)
    monkeypatch.setattr(rt, "generate_parsed", lambda cfg, s, u, sc: rt.Selected(
        record_ids=["2026-07-19_exp-000", "2026-07-19_exp-001", "2026-07-19_exp-002"]))
    res = rt.retrieve(Config(vault=tmp_path), "질의", top_k=2)
    assert len(res["records"]) == 2


def test_retrieve_empty_vault_no_llm_call(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("빈 볼트에서 LLM을 호출하면 안 됨")

    monkeypatch.setattr(rt, "generate_parsed", boom)
    assert rt.retrieve(Config(vault=tmp_path), "질의") == {"records": [], "wiki": []}


def test_catalog_includes_resolution(tmp_path, monkeypatch):
    rec = ExperimentRecord(
        id="2026-07-19_exp-solved", date="2026-07-19", experiment_type="스퍼터 증착",
        symptom=Symptom(category="low_value", description="낮음"),
        resolution=Resolution(resolved=True, actual_cause="타겟 산화"),
    )
    save_record(tmp_path, rec, "원문", "정리")
    captured = {}

    def fake_parsed(cfg, system, user, schema):
        captured["user"] = user
        return rt.Selected()

    monkeypatch.setattr(rt, "generate_parsed", fake_parsed)
    rt.retrieve(Config(vault=tmp_path), "질의")
    assert "해결: 타겟 산화" in captured["user"]


def test_retrieve_skips_corrupt_md(tmp_path, monkeypatch):
    make_vault(tmp_path, 1)
    (tmp_path / "raw" / "experiments" / "zz-corrupt.md").write_text("프론트매터 없는 메모", encoding="utf-8")
    monkeypatch.setattr(rt, "generate_parsed", lambda cfg, s, u, sc: rt.Selected(
        record_ids=["2026-07-19_exp-000"]))
    res = rt.retrieve(Config(vault=tmp_path), "질의")
    assert [r["id"] for r in res["records"]] == ["2026-07-19_exp-000"]


def test_hallucinations_do_not_consume_top_k(tmp_path, monkeypatch):
    make_vault(tmp_path, 3)
    monkeypatch.setattr(rt, "generate_parsed", lambda cfg, s, u, sc: rt.Selected(
        record_ids=["없는-1", "없는-2", "2026-07-19_exp-000", "2026-07-19_exp-001"]))
    res = rt.retrieve(Config(vault=tmp_path), "질의", top_k=2)
    assert [r["id"] for r in res["records"]] == ["2026-07-19_exp-000", "2026-07-19_exp-001"]


def test_catalog_includes_notes(tmp_path, monkeypatch):
    rec = ExperimentRecord(
        id="2026-08-05_exp-001", date="2026-08-05", experiment_type="증착",
        notes="증착 중 정전 발생")
    save_record(tmp_path, rec, "원문", "정리")
    captured = {}

    def fake_parsed(cfg, system, user, schema):
        captured["user"] = user
        return rt.Selected()

    monkeypatch.setattr(rt, "generate_parsed", fake_parsed)
    rt.retrieve(Config(vault=tmp_path), "질의")
    assert "특이사항: 증착 중 정전 발생" in captured["user"]
