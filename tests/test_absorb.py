import json

from horcrux import absorb as ab
from horcrux.config import Config
from horcrux.records import ExperimentRecord, Symptom, save_record


def make_rec(tmp_path, rid, equipment, category="low_value"):
    rec = ExperimentRecord(id=rid, date="2026-07-19", experiment_type="스퍼터 증착",
                           equipment=equipment, materials=["ITO 타겟"],
                           symptom=Symptom(category=category, description="문제"))
    save_record(tmp_path, rec, "원문", "정리")
    return rec


def test_group_targets():
    r = ExperimentRecord(id="a", date="d", experiment_type="스퍼터 증착",
                         equipment=["RF 스퍼터"], materials=["ITO 타겟"],
                         symptom=Symptom(category="low_value", description="x"))
    groups = ab.group_targets([r])
    assert ("equipment", "RF 스퍼터") in groups
    assert ("materials", "ITO 타겟") in groups
    assert ("failure-modes", "스퍼터 증착-값낮음") in groups


def test_group_targets_no_failure_mode_when_none():
    r = ExperimentRecord(id="a", date="d", equipment=["X"], symptom=Symptom(category="none"))
    groups = ab.group_targets([r])
    assert not any(k[0] == "failure-modes" for k in groups)


def test_absorb_writes_articles_and_is_idempotent(tmp_path, monkeypatch):
    calls = []

    def fake_generate(cfg, system, user):
        calls.append(user)
        return "아티클 본문"

    monkeypatch.setattr(ab, "generate", fake_generate)
    cfg = Config(vault=tmp_path)
    make_rec(tmp_path, "2026-07-19_sputter-001", ["RF 스퍼터"])
    n1 = ab.run_absorb(cfg)
    assert n1 == 3  # equipment 1 + materials 1 + failure-mode 1
    assert (tmp_path / "wiki" / "equipment" / "rf-스퍼터.md").exists()
    log = json.loads((tmp_path / "wiki" / "_absorb_log.json").read_text(encoding="utf-8"))
    assert "2026-07-19_sputter-001" in log
    # 두 번째 실행: 신규 레코드 없음 → 아무것도 안 함
    n2 = ab.run_absorb(cfg)
    assert n2 == 0
    assert len(calls) == 3


def test_absorb_updates_existing_article(tmp_path, monkeypatch):
    captured = []

    def fake_generate(cfg, system, user):
        captured.append(user)
        return "갱신된 아티클"

    monkeypatch.setattr(ab, "generate", fake_generate)
    cfg = Config(vault=tmp_path)
    make_rec(tmp_path, "2026-07-19_sputter-001", ["RF 스퍼터"])
    ab.run_absorb(cfg)
    captured.clear()
    make_rec(tmp_path, "2026-07-19_sputter-002", ["RF 스퍼터"])
    ab.run_absorb(cfg)
    # 기존 아티클 본문이 갱신 프롬프트에 포함되어야 함
    assert any("갱신된 아티클" in u for u in captured)


def test_absorb_skips_corrupt_md(tmp_path, monkeypatch):
    monkeypatch.setattr(ab, "generate", lambda cfg, s, u: "아티클")
    cfg = Config(vault=tmp_path)
    make_rec(tmp_path, "2026-07-19_sputter-001", ["RF 스퍼터"])
    (tmp_path / "raw" / "experiments" / "zz-note.md").write_text("옵시디언 메모", encoding="utf-8")
    assert ab.run_absorb(cfg) == 3  # 정상 레코드 1건만 편찬 (equipment+materials+failure-mode)


def test_absorb_skips_needs_review(tmp_path, monkeypatch):
    monkeypatch.setattr(ab, "generate", lambda cfg, s, u: "아티클")
    cfg = Config(vault=tmp_path)
    rec = ExperimentRecord(id="2026-07-19_raw-001", date="2026-07-19", equipment=["X"],
                           symptom=Symptom(category="low_value", description="문제"),
                           needs_review=True)
    save_record(tmp_path, rec, "원문", "(파싱 실패)")
    assert ab.run_absorb(cfg) == 0
    # absorb 로그에 기록되지 않아야 손편집 복구 후 자연 편찬됨
    assert not (tmp_path / "wiki" / "_absorb_log.json").exists()
