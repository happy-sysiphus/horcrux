import pytest

from horcrux import ingest
from horcrux.config import Config, VaultConfig
from horcrux.ingest import ParsedLog, missing_required, parse_log, to_record
from horcrux.records import Parameter, Symptom


DEFAULT_VC = VaultConfig(
    required_fields=["objective", "parameters", "results", "symptom", "actions_taken"],
    required_parameters=[],
)


def full_parsed():
    return ParsedLog(
        experiment_type="박막 증착", objective="ITO 증착",
        equipment=["RF 스퍼터"], parameters=[Parameter(name="RF power", value="150W")],
        results="증착률 5nm/min", summary="정리 서술",
        symptom=Symptom(category="none", description="문제 없음"),
    )


def test_missing_required_empty_log():
    gaps = missing_required(ParsedLog(), DEFAULT_VC)
    assert len(gaps) == 4  # 목적·공정변수·결과·증상. 조치는 문제없음(category=none)이라 통과


def test_missing_required_full_log():
    assert missing_required(full_parsed(), DEFAULT_VC) == []


def test_missing_required_respects_field_toggle():
    vc = VaultConfig(required_fields=["objective"], required_parameters=[])
    assert len(missing_required(ParsedLog(), vc)) == 1


def test_missing_required_actions_gate_when_problem():
    p = full_parsed()
    p.symptom = Symptom(category="low_value", description="증착률 낮음")
    p.actions_taken = []
    assert len(missing_required(p, DEFAULT_VC)) == 1  # 문제가 있는데 조치 미기재


def test_missing_required_lab_parameters():
    p = full_parsed()
    p.unrecorded_required_parameters = ["챔버 습도"]
    vc = VaultConfig(required_fields=[], required_parameters=["챔버 습도"])
    assert missing_required(p, vc) == ["연구실 필수 항목 '챔버 습도' 값을 알려주세요."]


def test_parse_log_passes_required_parameters_to_llm(monkeypatch):
    captured = {}

    def fake(cfg, system, user, schema):
        captured["user"] = user
        return full_parsed()

    monkeypatch.setattr(ingest, "generate_parsed", fake)
    vc = VaultConfig(required_fields=[], required_parameters=["기판 온도"])
    parse_log(Config(vault="v"), "로그", vc)
    assert "기판 온도" in captured["user"]


def test_parse_log_filters_hallucinated_parameters(monkeypatch):
    def fake(cfg, system, user, schema):
        p = full_parsed()
        p.unrecorded_required_parameters = ["챔버 습도", "엉뚱한 항목"]
        return p

    monkeypatch.setattr(ingest, "generate_parsed", fake)
    vc = VaultConfig(required_fields=[], required_parameters=["챔버 습도"])
    result = parse_log(Config(vault="v"), "로그", vc)
    assert result.unrecorded_required_parameters == ["챔버 습도"]


def test_parse_log_retries_once(monkeypatch):
    calls = []

    def flaky(cfg, system, user, schema):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("boom")
        return full_parsed()

    monkeypatch.setattr(ingest, "generate_parsed", flaky)
    result = parse_log(Config(vault="v"), "로그")
    assert result.objective == "ITO 증착"
    assert len(calls) == 2


def test_parse_log_raises_after_two_failures(monkeypatch):
    def always_fail(cfg, system, user, schema):
        raise ValueError("boom")

    monkeypatch.setattr(ingest, "generate_parsed", always_fail)
    with pytest.raises(ValueError):
        parse_log(Config(vault="v"), "로그")


def test_to_record_excludes_summary(tmp_path):
    rec = to_record(tmp_path, full_parsed(), "2026-07-19")
    assert rec.date == "2026-07-19"
    assert rec.objective == "ITO 증착"
    assert "summary" not in rec.model_dump()
    assert rec.id.startswith("2026-07-19_")
