import pytest

ALL_ENV = ("HORCRUX_VAULT", "HORCRUX_PROVIDER", "HORCRUX_MODEL")


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    # 모든 테스트에서 실제 ~/.horcrux/config.yaml·HORCRUX_* env 격리.
    # raising=False: Task 1 구현 전(_config_path 부재)에도 기존 테스트가 안 깨지게.
    from horcrux import config as config_mod
    p = tmp_path / "config.yaml"
    monkeypatch.setattr(config_mod, "_config_path", lambda: p, raising=False)
    for k in ALL_ENV:
        monkeypatch.delenv(k, raising=False)
    return p
