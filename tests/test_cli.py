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


def test_cli_bot_dispatch(monkeypatch):
    called = {}
    import horcrux.bot as bot_mod
    monkeypatch.setattr(bot_mod, "run_bot", lambda cfg: called.setdefault("cfg", cfg))
    from horcrux.cli import main
    main(["bot"])
    assert "cfg" in called
