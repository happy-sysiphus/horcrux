from horcrux import feedback as fb
from horcrux.config import Config
from horcrux.records import ExperimentRecord, SuspectedCause, load_record, record_path, save_record


def test_run_feedback_updates(tmp_path):
    rec = ExperimentRecord(id="2026-07-19_x-001", date="2026-07-19",
                           suspected_causes=[SuspectedCause(cause="타겟 산화")])
    save_record(tmp_path, rec, "원문", "정리")
    msg = fb.run_feedback(Config(vault=tmp_path), rec.id, True, "타겟 산화", "연마 후 해결")
    assert "해결로 기록됨" in msg and "타겟 산화" in msg
    loaded, _ = load_record(record_path(tmp_path, rec.id))
    assert loaded.resolution.resolved is True
    assert loaded.resolution.actual_cause == "타겟 산화"
    assert loaded.suspected_causes[0].status == "confirmed"


def test_run_feedback_missing_record(tmp_path):
    msg = fb.run_feedback(Config(vault=tmp_path), "없는-id", True, None, "")
    assert "찾을 수 없음" in msg
