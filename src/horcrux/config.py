from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    vault: Path
    provider: str = "claude"
    model: str = "claude-opus-4-8"

    def __post_init__(self):
        self.vault = Path(self.vault)


def load_config() -> Config:
    return Config(
        vault=Path(os.environ.get("HORCRUX_VAULT", "example-vault")),
        provider=os.environ.get("HORCRUX_PROVIDER", "claude"),
        model=os.environ.get("HORCRUX_MODEL", "claude-opus-4-8"),
    )


# §2a — 구조 카테고리 하드 게이트 후보 (볼트 config.yaml의 required_fields가 이 중에서 선택)
GATEABLE_FIELDS = ["objective", "parameters", "results", "symptom", "actions_taken"]


@dataclass
class VaultConfig:
    required_fields: list[str]
    required_parameters: list[str]


def load_vault_config(vault: Path) -> VaultConfig:
    p = Path(vault) / "config.yaml"
    data = {}
    if p.exists():
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return VaultConfig(
        required_fields=list(data.get("required_fields", GATEABLE_FIELDS)),
        required_parameters=list(data.get("required_parameters", [])),
    )
