import pytest
from pydantic import BaseModel

from horcrux.config import GATEABLE_FIELDS, Config, load_config, load_vault_config
from horcrux.llm import generate, generate_parsed


def test_load_config_defaults(monkeypatch):
    for k in ("HORCRUX_VAULT", "HORCRUX_PROVIDER", "HORCRUX_MODEL"):
        monkeypatch.delenv(k, raising=False)
    cfg = load_config()
    assert cfg.provider == "claude"
    assert cfg.model == "claude-opus-4-8"
    assert str(cfg.vault) == "example-vault"


def test_load_config_env_override(monkeypatch):
    monkeypatch.setenv("HORCRUX_VAULT", "my-lab")
    monkeypatch.setenv("HORCRUX_PROVIDER", "gemini")
    cfg = load_config()
    assert str(cfg.vault) == "my-lab"
    assert cfg.provider == "gemini"


def test_vault_config_defaults(tmp_path):
    vc = load_vault_config(tmp_path)
    assert vc.required_fields == GATEABLE_FIELDS
    assert vc.required_parameters == []


def test_vault_config_from_yaml(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "required_fields: [objective, results]\nrequired_parameters:\n  - 챔버 습도\n",
        encoding="utf-8",
    )
    vc = load_vault_config(tmp_path)
    assert vc.required_fields == ["objective", "results"]
    assert vc.required_parameters == ["챔버 습도"]


def test_vault_config_null_keys(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "required_fields:\nrequired_parameters:\n", encoding="utf-8")
    vc = load_vault_config(tmp_path)
    assert vc.required_fields == GATEABLE_FIELDS
    assert vc.required_parameters == []


def test_unknown_provider_raises():
    cfg = Config(vault="v", provider="gemini")

    class Out(BaseModel):
        x: int = 0

    with pytest.raises(NotImplementedError):
        generate(cfg, "s", "u")
    with pytest.raises(NotImplementedError):
        generate_parsed(cfg, "s", "u", Out)
