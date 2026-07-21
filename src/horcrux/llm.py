from __future__ import annotations

from pydantic import BaseModel

from .config import Config

_client = None


def _claude():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


# ponytail: provider 분기가 함수마다 if 한 줄 — 제미니 추가 시 이 파일에만 elif 추가

def generate(cfg: Config, system: str, user: str) -> str:
    if cfg.provider == "claude":
        resp = _claude().messages.create(
            model=cfg.model, max_tokens=16000, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return next(b.text for b in resp.content if b.type == "text")
    raise NotImplementedError(f"provider '{cfg.provider}' 미구현 — llm.py에 어댑터 추가 필요")


def generate_parsed(cfg: Config, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    if cfg.provider == "claude":
        resp = _claude().messages.parse(
            model=cfg.model, max_tokens=16000, system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        if resp.parsed_output is None:
            raise ValueError("구조화 출력 파싱 실패")
        return resp.parsed_output
    raise NotImplementedError(f"provider '{cfg.provider}' 미구현 — llm.py에 어댑터 추가 필요")
