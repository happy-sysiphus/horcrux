import pytest

from horcrux import cli


def test_log_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("HORCRUX_VAULT", str(tmp_path))
    called = {}
    monkeypatch.setattr(cli, "run_log", lambda cfg: called.setdefault("ok", True))
    cli.main(["log"])
    assert called.get("ok")


def test_unknown_command_exits():
    with pytest.raises(SystemExit):
        cli.main(["nope"])


def test_log_chains_absorb(tmp_path, monkeypatch):
    import horcrux.absorb as absorb_mod

    monkeypatch.setenv("HORCRUX_VAULT", str(tmp_path))
    monkeypatch.setattr(cli, "run_log", lambda cfg: tmp_path / "x.md")
    called = {}
    monkeypatch.setattr(absorb_mod, "run_absorb", lambda cfg: called.setdefault("n", 2))
    cli.main(["log"])
    assert called.get("n") == 2
