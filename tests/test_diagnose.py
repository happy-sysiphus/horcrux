from horcrux import diagnose as dg
from horcrux.config import Config


def test_answer_includes_selected_cases(tmp_path, monkeypatch):
    from horcrux.records import ExperimentRecord, save_record

    rec = ExperimentRecord(id="2026-07-19_sputter-001", date="2026-07-19",
                           equipment=["RF 스퍼터"], experiment_type="스퍼터 증착")
    path = save_record(tmp_path, rec, "원문", "정리")
    monkeypatch.setattr(dg, "retrieve", lambda cfg, q, **kw: {
        "records": [{"id": rec.id, "path": str(path)}], "wiki": []})
    captured = {}

    def fake_generate(cfg, system, user):
        captured["user"] = user
        return "진단 응답"

    monkeypatch.setattr(dg, "generate", fake_generate)
    out = dg.diagnose(Config(vault=tmp_path), "증착률이 낮아요")
    assert out == "진단 응답"
    assert "2026-07-19_sputter-001" in captured["user"]  # 사례 전문이 컨텍스트에 포함


def test_wiki_articles_included_in_context(tmp_path, monkeypatch):
    art = tmp_path / "wiki" / "equipment" / "rf-스퍼터.md"
    art.parent.mkdir(parents=True)
    art.write_text("---\nname: RF 스퍼터\n---\n\n장비 노하우 본문", encoding="utf-8")
    monkeypatch.setattr(dg, "retrieve", lambda cfg, q, **kw: {
        "records": [], "wiki": [{"id": "equipment/rf-스퍼터", "path": str(art)}]})
    captured = {}

    def fake_generate(cfg, system, user):
        captured["user"] = user
        return "응답"

    monkeypatch.setattr(dg, "generate", fake_generate)
    dg.diagnose(Config(vault=tmp_path), "질문")
    assert "장비 노하우 본문" in captured["user"]


def test_no_cases_labelled_general(tmp_path, monkeypatch):
    monkeypatch.setattr(dg, "retrieve", lambda cfg, q, **kw: {"records": [], "wiki": []})
    monkeypatch.setattr(dg, "generate", lambda cfg, s, u: "일반 지식 응답")
    out = dg.diagnose(Config(vault=tmp_path), "질문")
    assert "축적된 유사 사례가 없" in out


def test_wiki_only_labelled_wiki_based(tmp_path, monkeypatch):
    art = tmp_path / "wiki" / "equipment" / "x.md"
    art.parent.mkdir(parents=True)
    art.write_text("---\nname: X\n---\n\n본문", encoding="utf-8")
    monkeypatch.setattr(dg, "retrieve", lambda cfg, q, **kw: {
        "records": [], "wiki": [{"id": "equipment/x", "path": str(art)}]})
    monkeypatch.setattr(dg, "generate", lambda cfg, s, u: "응답")
    out = dg.diagnose(Config(vault=tmp_path), "질문")
    assert "위키 아티클 기반" in out
    assert "일반 지식" not in out


def test_answer_strips_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(dg, "retrieve", lambda cfg, q, **kw: {"records": [], "wiki": []})
    monkeypatch.setattr(
        dg, "generate",
        lambda cfg, s, u: "## 원인 후보\n**전구체 열화**가 유력합니다.\n- 확인: **개봉일** 점검")
    d = dg.diagnose_data(Config(vault=tmp_path), "질문")
    assert "**" not in d["answer"]
    assert "##" not in d["answer"]
    assert "전구체 열화가 유력합니다." in d["answer"]


def test_diagnose_data_shape(tmp_path, monkeypatch):
    from horcrux.records import ExperimentRecord, save_record, record_path

    rec = ExperimentRecord(id="2026-08-01_exp-001", date="2026-08-01", experiment_type="증착")
    save_record(tmp_path, rec, "원문", "요약")
    monkeypatch.setattr(dg, "retrieve", lambda cfg, q, **kw: {
        "records": [{"id": rec.id, "path": str(record_path(tmp_path, rec.id))}], "wiki": []})
    monkeypatch.setattr(dg, "generate", lambda cfg, s, u: "답변")
    d = dg.diagnose_data(Config(vault=tmp_path), "질문")
    assert d["evidence"] == "records"
    assert d["records"][0]["id"] == rec.id
    assert d["answer"] == "답변"
