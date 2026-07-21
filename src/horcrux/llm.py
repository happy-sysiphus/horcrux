from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel

from .config import Config

PROVIDERS = ("claude", "gemini", "codex")
_TIMEOUT = 300  # 초 — CLI 무응답 행 방지


def _exe(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(
            f"'{name}' CLI를 찾을 수 없음 — 설치·로그인 후 재시도 (HORCRUX_PROVIDER={name})"
        )
    return path


def _run(cmd: list[str], prompt: str) -> str:
    p = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    try:
        out, err = p.communicate(prompt, timeout=_TIMEOUT)
    except subprocess.TimeoutExpired:
        # npm .cmd shim은 실제 CLI가 손자 프로세스 — 직계만 죽이면 파이프 대기로 무한 블록.
        # Windows는 taskkill /T로 프로세스 트리 전체 종료.
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        else:
            p.kill()
        p.communicate()
        raise RuntimeError(f"{cmd[0]} 응답 없음 — {_TIMEOUT}초 초과") from None
    if p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} 실패 (exit {p.returncode}): {err.strip()[-500:]}")
    return out.strip()


def generate(cfg: Config, system: str, user: str) -> str:
    # 프롬프트는 stdin으로 전달 — Windows 커맨드라인 길이 제한 회피
    prompt = f"{system}\n\n{user}"
    model = ["--model", cfg.model] if cfg.model else []
    if cfg.provider == "claude":
        return _run([_exe("claude"), "-p", *model], prompt)
    if cfg.provider == "gemini":
        return _run([_exe("gemini"), *model], prompt)  # stdin 파이프 = headless
    if cfg.provider == "codex":
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "last.txt"
            _run(
                [_exe("codex"), "exec", "-", "--skip-git-repo-check", "--ephemeral",
                 "--sandbox", "read-only", "-o", str(out), *model],
                prompt,
            )
            # codex stdout은 진행 로그 포함 — 최종 메시지는 -o 파일이 정본
            return out.read_text(encoding="utf-8").strip()
    raise NotImplementedError(f"provider '{cfg.provider}' 미지원 — {PROVIDERS} 중 선택")


_JSON_INSTR = (
    "\n\n응답은 아래 JSON 스키마에 맞는 JSON 객체 하나만 출력하라. 코드펜스·설명·주석 금지.\n"
    "스키마: {schema}"
)


def _extract_json(text: str) -> str:
    # 후보 순서대로 json.loads로 검증해 첫 유효 JSON 반환 — 펜스 태그 대소문자,
    # 문자열 필드 안 ``` 절단, 전후 산문 케이스 전부 커버
    candidates = []
    m = re.search(r"```[^\n]*\n(.*?)```", text, re.DOTALL)
    if m:
        candidates.append(m.group(1).strip())
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e > s:
        candidates.append(text[s:e + 1])
    candidates.append(text.strip())
    for c in candidates:
        try:
            json.loads(c)
            return c
        except ValueError:
            continue
    return candidates[-1]


def generate_parsed(cfg: Config, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    instr = _JSON_INSTR.format(
        schema=json.dumps(schema.model_json_schema(), ensure_ascii=False)
    )
    raw = generate(cfg, system + instr, user)
    try:
        return schema.model_validate_json(_extract_json(raw))
    except Exception:
        # CLI는 스키마 강제가 없어 파싱 실패가 일상적 — 어댑터에서 1회 재생성 (모든 호출부 커버)
        raw = generate(cfg, system + instr, user)
        return schema.model_validate_json(_extract_json(raw))
