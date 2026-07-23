import pytest
import yaml

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


def test_cli_bot_without_token_exits_clean(monkeypatch, isolated_config, capsys):
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    from horcrux.cli import main
    with pytest.raises(SystemExit) as ei:
        main(["bot"])
    assert ei.value.code == 1
    err = capsys.readouterr().err
    assert "토큰" in err   # 깔끔한 메시지, 트레이스백 아님


def test_cli_init_writes_config(monkeypatch, isolated_config):
    answers = iter(["tok-1", "C:/lab/vault", "gemini", "", "lab-log", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    from horcrux.cli import main
    main(["init"])
    data = yaml.safe_load(isolated_config.read_text(encoding="utf-8"))
    assert data["discord_token"] == "tok-1"
    assert data["vault"] == "C:/lab/vault"
    assert data["provider"] == "gemini"
    assert data["model"] is None          # 빈 입력 + 기존값 없음 = None
    assert data["log_channel"] == "lab-log"
    assert data["ask_channel"] == "질문"   # 빈 입력 = 기본값 유지


def test_cli_init_keeps_existing_on_empty(monkeypatch, isolated_config):
    isolated_config.write_text(yaml.safe_dump({
        "discord_token": "tok-old", "vault": "C:/old", "provider": "codex",
        "model": "o3", "log_channel": "L", "ask_channel": "A",
    }, allow_unicode=True), encoding="utf-8")
    answers = iter(["", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    from horcrux.cli import main
    main(["init"])
    data = yaml.safe_load(isolated_config.read_text(encoding="utf-8"))
    assert data == {"discord_token": "tok-old", "vault": "C:/old", "provider": "codex",
                    "model": "o3", "log_channel": "L", "ask_channel": "A"}
