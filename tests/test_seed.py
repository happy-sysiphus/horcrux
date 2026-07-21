from horcrux import seed as sd
from horcrux.config import Config
from horcrux.ingest import ParsedLog
from horcrux.records import Parameter, list_records


def test_run_seed_saves_records(tmp_path, monkeypatch):
    def fake_generate_parsed(cfg, system, user, schema):
        if schema is sd.SeedBatch:
            return sd.SeedBatch(logs=["로그 하나", "로그 둘"])
        return ParsedLog(experiment_type="스퍼터 증착", objective="목적",
                         equipment=["RF 스퍼터"], parameters=[Parameter(name="p", value="v")],
                         results="결과", summary="정리")

    monkeypatch.setattr(sd, "generate_parsed", fake_generate_parsed)
    monkeypatch.setattr(sd.ingest_mod, "generate_parsed", fake_generate_parsed)
    monkeypatch.setattr(sd, "run_absorb", lambda cfg: 0)
    cfg = Config(vault=tmp_path)
    n = sd.run_seed(cfg, 2)
    assert n == 2
    assert len(list_records(tmp_path)) == 2
