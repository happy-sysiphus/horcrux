# Horcrux MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** wet lab 실험 로그를 LLM으로 구조화해 마크다운 볼트에 저장하고, 유사 사례 검색 + 위키 편찬으로 문제 진단을 보조하는 CLI 파이프라인.

**Architecture:** md 파일(frontmatter)이 진실의 원천, `.index/`는 파생 검색 캐시. 생성 LLM은 `llm.py` 어댑터로 격리(클로드 기본, 제미니 교체 대비). 임베딩은 로컬 sentence-transformers. 스펙: `docs/superpowers/specs/2026-07-19-horcrux-mvp-design.md`.

**Tech Stack:** Python 3.10+, anthropic SDK, pydantic v2, pyyaml, numpy, sentence-transformers, pytest.

## Global Constraints

- 생성 모델 기본값: `claude-opus-4-8` (환경변수 `HORCRUX_MODEL`로 교체)
- 검색 모드: `HORCRUX_SEARCH` = auto|llm|vector (기본 auto — 레코드 수 ≤ `HORCRUX_SEARCH_THRESHOLD`(기본 200)이면 LLM-select, 초과면 vector). diagnose는 `retrieval.retrieve()`만 호출
- 임베딩: 어댑터(`embeddings.py`). `HORCRUX_EMBED_PROVIDER` = local|gemini|voyage (기본 local — sentence-transformers, gemini/voyage는 NotImplementedError 자리만). `HORCRUX_EMBED_MODEL` 기본 `google/embeddinggemma-300m` (HF 게이트 접근 불가 시 env로 `intfloat/multilingual-e5-small` 폴백). sentence-transformers는 optional extra `[vector]`
- 하드 게이트(§2a): 볼트 `config.yaml`의 `required_fields`(5개 구조 카테고리 중 선택, 기본 전부)와 `required_parameters`(연구실 커스텀 필수 파라미터). 의미 매칭은 LLM(파싱 시 미기재 보고), 게이트 판단은 코드(보고를 설정 목록과 대조, 목록 밖 이름은 무시)
- 모든 파일 I/O는 `encoding="utf-8"` 명시 (Windows cp949 환경)
- 단위 테스트는 API 호출·모델 다운로드 없이 통과해야 함 (LLM·임베더 monkeypatch)
- anthropic 구조화 출력은 `client.messages.parse(..., output_format=<PydanticModel>)` → `response.parsed_output`
- 커밋 메시지 끝에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 추가

---

### Task 1: 프로젝트 스캐폴드 + records 모듈

**Files:**
- Create: `pyproject.toml`
- Create: `src/horcrux/__init__.py` (빈 파일)
- Create: `src/horcrux/records.py`
- Test: `tests/test_records.py`

**Interfaces:**
- Consumes: 없음 (최초 태스크)
- Produces: `ExperimentRecord`, `Parameter`, `Symptom`, `SuspectedCause`, `Resolution` (pydantic 모델); `save_record(vault: Path, rec, raw_log: str, summary: str) -> Path`; `load_record(path: Path) -> tuple[ExperimentRecord, str]`; `list_records(vault: Path) -> list[Path]`; `record_path(vault, record_id) -> Path`; `update_resolution(vault, record_id, resolved: bool, actual_cause: str | None, note: str = "") -> ExperimentRecord`; `make_record_id(vault, date: str, label: str) -> str`; `slugify(label: str) -> str`; `write_md(path, meta: dict, body: str)`; `read_md(path) -> tuple[dict, str]`

- [ ] **Step 1: pyproject.toml 작성**

```toml
[project]
name = "horcrux"
version = "0.1.0"
description = "연구실 실험 기록·문제 진단 CLI"
requires-python = ">=3.10"
dependencies = [
    "anthropic",
    "pydantic>=2",
    "pyyaml",
    "numpy",
]

[project.optional-dependencies]
dev = ["pytest"]
vector = ["sentence-transformers"]

[project.scripts]
horcrux = "horcrux.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: 설치**

`src/horcrux/__init__.py` 빈 파일을 먼저 만든 뒤:

Run: `pip install -e ".[dev]"`
Expected: 성공 (sentence-transformers 설치는 오래 걸릴 수 있음)

- [ ] **Step 3: 실패하는 테스트 작성** — `tests/test_records.py`

```python
from horcrux.records import (
    ExperimentRecord, Parameter, Resolution, SuspectedCause, Symptom,
    list_records, load_record, make_record_id, save_record, update_resolution,
)


def sample_record(rid="2026-07-19_test-001"):
    return ExperimentRecord(
        id=rid, date="2026-07-19", experiment_type="박막 증착",
        objective="ITO 박막 증착", equipment=["RF 스퍼터"], materials=["ITO 타겟"],
        parameters=[Parameter(name="RF power", value="150W", controllable=True)],
        results="증착률 5nm/min",
        symptom=Symptom(category="low_value", description="증착률이 평소보다 낮음"),
        suspected_causes=[SuspectedCause(cause="타겟 표면 산화")],
        actions_taken=["타겟 표면 확인"],
    )


def test_roundtrip(tmp_path):
    rec = sample_record()
    path = save_record(tmp_path, rec, "원문 로그입니다", "정리 서술입니다")
    loaded, body = load_record(path)
    assert loaded == rec
    assert "원문 로그입니다" in body
    assert "정리 서술입니다" in body
    assert list_records(tmp_path) == [path]


def test_update_resolution_confirms_cause(tmp_path):
    rec = sample_record()
    rec.suspected_causes.append(SuspectedCause(cause="가스 유량 오류"))
    save_record(tmp_path, rec, "원문", "정리")
    updated = update_resolution(tmp_path, rec.id, True, "타겟 표면 산화", note="연마 후 정상")
    assert updated.resolution == Resolution(resolved=True, actual_cause="타겟 표면 산화", note="연마 후 정상")
    statuses = {c.cause: c.status for c in updated.suspected_causes}
    assert statuses == {"타겟 표면 산화": "confirmed", "가스 유량 오류": "rejected"}
    # 디스크에도 반영
    reloaded, _ = load_record(tmp_path / "raw" / "experiments" / f"{rec.id}.md")
    assert reloaded.resolution.resolved is True


def test_update_resolution_new_cause_appended(tmp_path):
    rec = sample_record()
    save_record(tmp_path, rec, "원문", "정리")
    updated = update_resolution(tmp_path, rec.id, True, "기판 오염")
    assert any(c.cause == "기판 오염" and c.status == "confirmed" for c in updated.suspected_causes)


def test_make_record_id_unique(tmp_path):
    rid1 = make_record_id(tmp_path, "2026-07-19", "박막 증착")
    save_record(tmp_path, sample_record(rid1), "원문", "정리")
    rid2 = make_record_id(tmp_path, "2026-07-19", "박막 증착")
    assert rid1 != rid2
    assert rid1.startswith("2026-07-19_") and rid2.endswith("-002")
```

- [ ] **Step 4: 실패 확인**

Run: `pytest tests/test_records.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'horcrux.records'`

- [ ] **Step 5: 구현** — `src/horcrux/records.py`

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class Parameter(BaseModel):
    name: str
    value: str
    controllable: bool = True


class Symptom(BaseModel):
    category: Literal["low_value", "unstable", "abnormal", "none"] = "none"
    description: str = ""


class SuspectedCause(BaseModel):
    cause: str
    status: Literal["unconfirmed", "confirmed", "rejected"] = "unconfirmed"


class Resolution(BaseModel):
    resolved: bool = False
    actual_cause: str | None = None
    note: str = ""


class ExperimentRecord(BaseModel):
    id: str
    date: str
    experiment_type: str = ""
    objective: str = ""
    equipment: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    results: str = ""
    symptom: Symptom = Field(default_factory=Symptom)
    suspected_causes: list[SuspectedCause] = Field(default_factory=list)
    actions_taken: list[str] = Field(default_factory=list)
    resolution: Resolution = Field(default_factory=Resolution)
    needs_review: bool = False


def records_dir(vault: Path) -> Path:
    return vault / "raw" / "experiments"


def record_path(vault: Path, record_id: str) -> Path:
    return records_dir(vault) / f"{record_id}.md"


def slugify(label: str) -> str:
    return re.sub(r"[^\w가-힣]+", "-", label).strip("-").lower() or "exp"


def make_record_id(vault: Path, date: str, label: str) -> str:
    slug = slugify(label)
    n = 1
    while record_path(vault, f"{date}_{slug}-{n:03d}").exists():
        n += 1
    return f"{date}_{slug}-{n:03d}"


def write_md(path: Path, meta: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{fm}---\n\n{body}\n", encoding="utf-8")


def read_md(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm), body.strip()


def save_record(vault: Path, rec: ExperimentRecord, raw_log: str, summary: str) -> Path:
    body = f"## 원문 로그\n\n{raw_log}\n\n## 정리\n\n{summary}"
    path = record_path(vault, rec.id)
    write_md(path, rec.model_dump(), body)
    return path


def load_record(path: Path) -> tuple[ExperimentRecord, str]:
    meta, body = read_md(path)
    return ExperimentRecord.model_validate(meta), body


def list_records(vault: Path) -> list[Path]:
    d = records_dir(vault)
    return sorted(d.glob("*.md")) if d.exists() else []


def update_resolution(
    vault: Path, record_id: str, resolved: bool,
    actual_cause: str | None, note: str = "",
) -> ExperimentRecord:
    path = record_path(vault, record_id)
    rec, body = load_record(path)
    rec.resolution = Resolution(resolved=resolved, actual_cause=actual_cause, note=note)
    if actual_cause:
        for c in rec.suspected_causes:
            c.status = "confirmed" if c.cause == actual_cause else "rejected"
        if all(c.cause != actual_cause for c in rec.suspected_causes):
            rec.suspected_causes.append(SuspectedCause(cause=actual_cause, status="confirmed"))
    write_md(path, rec.model_dump(), body)
    return rec
```

- [ ] **Step 6: 통과 확인**

Run: `pytest tests/test_records.py -v`
Expected: 4 passed

- [ ] **Step 7: 커밋**

```bash
git add pyproject.toml src/horcrux/__init__.py src/horcrux/records.py tests/test_records.py
git commit -m "feat: 프로젝트 스캐폴드 + 실험 레코드 md 저장/로드"
```

---

### Task 2: config + LLM 어댑터

**Files:**
- Create: `src/horcrux/config.py`
- Create: `src/horcrux/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: 없음
- Produces: `Config` (필드: `vault: Path`, `provider: str`, `model: str`, `embed_provider: str`, `embed_model: str`, `search_mode: str`, `search_threshold: int`); `load_config() -> Config`; `GATEABLE_FIELDS: list[str]` (5개 구조 카테고리); `VaultConfig` (필드: `required_fields: list[str]`, `required_parameters: list[str]`); `load_vault_config(vault: Path) -> VaultConfig` (볼트 `config.yaml` 로드, 없으면 기본값 = 5개 전부·커스텀 없음); `generate(cfg, system: str, user: str) -> str`; `generate_parsed(cfg, system: str, user: str, schema: type[BaseModel]) -> BaseModel`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_llm.py`

```python
import pytest
from pydantic import BaseModel

from horcrux.config import GATEABLE_FIELDS, Config, load_config, load_vault_config
from horcrux.llm import generate, generate_parsed


def test_load_config_defaults(monkeypatch):
    for k in ("HORCRUX_VAULT", "HORCRUX_PROVIDER", "HORCRUX_MODEL", "HORCRUX_EMBED_PROVIDER",
              "HORCRUX_EMBED_MODEL", "HORCRUX_SEARCH", "HORCRUX_SEARCH_THRESHOLD"):
        monkeypatch.delenv(k, raising=False)
    cfg = load_config()
    assert cfg.provider == "claude"
    assert cfg.model == "claude-opus-4-8"
    assert str(cfg.vault) == "example-vault"
    assert cfg.embed_provider == "local"
    assert cfg.search_mode == "auto"
    assert cfg.search_threshold == 200


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


def test_unknown_provider_raises():
    cfg = Config(vault="v", provider="gemini")

    class Out(BaseModel):
        x: int = 0

    with pytest.raises(NotImplementedError):
        generate(cfg, "s", "u")
    with pytest.raises(NotImplementedError):
        generate_parsed(cfg, "s", "u", Out)
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `src/horcrux/config.py`

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    vault: Path
    provider: str = "claude"
    model: str = "claude-opus-4-8"
    embed_provider: str = "local"  # local | gemini | voyage
    embed_model: str = "google/embeddinggemma-300m"
    search_mode: str = "auto"      # auto | llm | vector
    search_threshold: int = 200

    def __post_init__(self):
        self.vault = Path(self.vault)


def load_config() -> Config:
    return Config(
        vault=Path(os.environ.get("HORCRUX_VAULT", "example-vault")),
        provider=os.environ.get("HORCRUX_PROVIDER", "claude"),
        model=os.environ.get("HORCRUX_MODEL", "claude-opus-4-8"),
        embed_provider=os.environ.get("HORCRUX_EMBED_PROVIDER", "local"),
        embed_model=os.environ.get("HORCRUX_EMBED_MODEL", "google/embeddinggemma-300m"),
        search_mode=os.environ.get("HORCRUX_SEARCH", "auto"),
        search_threshold=int(os.environ.get("HORCRUX_SEARCH_THRESHOLD", "200")),
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
```

- [ ] **Step 4: 구현** — `src/horcrux/llm.py`

```python
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
```

- [ ] **Step 5: 통과 확인**

Run: `pytest tests/test_llm.py -v`
Expected: 5 passed

- [ ] **Step 6: 커밋**

```bash
git add src/horcrux/config.py src/horcrux/llm.py tests/test_llm.py
git commit -m "feat: 설정 + 생성 LLM 어댑터 (클로드 기본, 제미니 교체 대비)"
```

---

### Task 3: 임베딩 어댑터 + 벡터 인덱서

**Files:**
- Create: `src/horcrux/embeddings.py`
- Create: `src/horcrux/indexer.py`
- Test: `tests/test_embeddings.py`
- Test: `tests/test_indexer.py`

**Interfaces:**
- Consumes: `records.list_records/load_record/ExperimentRecord`, `config.Config`
- Produces: `embeddings.embed(cfg, texts: list[str]) -> np.ndarray` — `cfg.embed_provider` 분기: local(sentence-transformers 지연 임포트) 구현, gemini/voyage는 NotImplementedError; `indexer.build_index(cfg) -> int` (색인 수, `.index/model.txt`에 임베딩 모델명 기록); `indexer.search(cfg, query: str, equipment: list[str] | None = None, materials: list[str] | None = None, symptom: str | None = None, top_k: int = 3) -> list[dict]` — 각 dict는 `{id, path, experiment_type, equipment, materials, symptom_category, score}`, 인덱스의 임베딩 모델이 현재 설정과 다르면 RuntimeError("reindex 필요"). indexer는 `from .embeddings import embed`로 가져와 모듈 전역 이름으로 호출 (테스트는 `monkeypatch.setattr(indexer, "embed", fake)`)

- [ ] **Step 0: 임베딩 어댑터 (테스트 + 구현)**

`tests/test_embeddings.py`:

```python
import pytest

from horcrux.config import Config
from horcrux.embeddings import embed


def test_unimplemented_provider_raises():
    with pytest.raises(NotImplementedError):
        embed(Config(vault="v", embed_provider="gemini"), ["x"])
```

`src/horcrux/embeddings.py`:

```python
from __future__ import annotations

import numpy as np

from .config import Config

_model = None


# ponytail: 생성 LLM 어댑터와 동일 패턴 — 클라우드 제공자(gemini/voyage) 추가 시 이 파일에만 elif
def embed(cfg: Config, texts: list[str]) -> np.ndarray:
    if cfg.embed_provider == "local":
        global _model
        if _model is None:
            from sentence_transformers import SentenceTransformer  # optional extra [vector]
            _model = SentenceTransformer(cfg.embed_model)
        return np.asarray(_model.encode(texts, normalize_embeddings=True), dtype=np.float32)
    raise NotImplementedError(f"embed provider '{cfg.embed_provider}' 미구현 — embeddings.py에 추가")
```

Run: `pytest tests/test_embeddings.py -v`
Expected: 1 passed

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_indexer.py`

```python
import numpy as np
import pytest

from horcrux import indexer
from horcrux.config import Config
from horcrux.records import ExperimentRecord, Symptom, save_record


def fake_embed(cfg, texts):
    vocab = ["스퍼터", "졸겔", "증착", "합성"]
    out = []
    for t in texts:
        v = np.array([float(t.count(w)) for w in vocab], dtype=np.float32) + 0.01
        out.append(v / np.linalg.norm(v))
    return np.vstack(out)


def make_vault(tmp_path):
    r1 = ExperimentRecord(
        id="2026-07-19_sputter-001", date="2026-07-19", experiment_type="스퍼터 증착",
        equipment=["RF 스퍼터"], materials=["ITO 타겟"],
        symptom=Symptom(category="low_value", description="증착률 낮음"),
    )
    r2 = ExperimentRecord(
        id="2026-07-19_solgel-001", date="2026-07-19", experiment_type="졸겔 합성",
        equipment=["핫플레이트"], materials=["TTIP"],
        symptom=Symptom(category="unstable", description="점도 불안정"),
    )
    save_record(tmp_path, r1, "스퍼터 증착 로그", "스퍼터 정리")
    save_record(tmp_path, r2, "졸겔 합성 로그", "졸겔 정리")
    return tmp_path


def test_build_and_search(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "embed", fake_embed)
    cfg = Config(vault=make_vault(tmp_path))
    assert indexer.build_index(cfg) == 2
    hits = indexer.search(cfg, "스퍼터 증착률이 낮아요")
    assert hits[0]["id"] == "2026-07-19_sputter-001"
    assert hits[0]["score"] >= hits[-1]["score"]


def test_equipment_filter(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "embed", fake_embed)
    cfg = Config(vault=make_vault(tmp_path))
    indexer.build_index(cfg)
    hits = indexer.search(cfg, "합성 문제", equipment=["핫플레이트"])
    assert [h["id"] for h in hits] == ["2026-07-19_solgel-001"]


def test_filter_fallback_to_all(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "embed", fake_embed)
    cfg = Config(vault=make_vault(tmp_path))
    indexer.build_index(cfg)
    hits = indexer.search(cfg, "스퍼터", equipment=["존재하지 않는 장비"])
    assert len(hits) == 2  # 필터 결과가 비면 전체에서 랭킹


def test_search_empty_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "embed", fake_embed)
    cfg = Config(vault=tmp_path)
    assert indexer.build_index(cfg) == 0
    assert indexer.search(cfg, "아무거나") == []


def test_embed_model_mismatch_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "embed", fake_embed)
    indexer.build_index(Config(vault=make_vault(tmp_path)))
    with pytest.raises(RuntimeError):
        indexer.search(Config(vault=tmp_path, embed_model="다른-모델"), "스퍼터")
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_indexer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `src/horcrux/indexer.py`

```python
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .config import Config
from .embeddings import embed
from .records import ExperimentRecord, list_records, load_record


def index_dir(vault: Path) -> Path:
    return vault / ".index"


def _record_text(rec: ExperimentRecord, body: str) -> str:
    return f"{rec.experiment_type}\n{rec.objective}\n{rec.results}\n{rec.symptom.description}\n{body}"


# ponytail: 매번 전체 재빌드 — 레코드 수천 건 넘으면 콘텐츠 해시 기반 증분으로
def build_index(cfg: Config) -> int:
    entries, texts = [], []
    for path in list_records(cfg.vault):
        rec, body = load_record(path)
        entries.append({
            "id": rec.id,
            "path": str(path),
            "experiment_type": rec.experiment_type,
            "equipment": rec.equipment,
            "materials": rec.materials,
            "symptom_category": rec.symptom.category,
        })
        texts.append(_record_text(rec, body))
    d = index_dir(cfg.vault)
    d.mkdir(parents=True, exist_ok=True)
    if texts:
        np.save(d / "embeddings.npy", embed(cfg, texts))
    (d / "meta.json").write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    (d / "model.txt").write_text(cfg.embed_model, encoding="utf-8")
    return len(entries)


def search(
    cfg: Config, query: str,
    equipment: list[str] | None = None,
    materials: list[str] | None = None,
    symptom: str | None = None,
    top_k: int = 3,
) -> list[dict]:
    d = index_dir(cfg.vault)
    if not (d / "meta.json").exists():
        return []
    indexed_model = (d / "model.txt").read_text(encoding="utf-8") if (d / "model.txt").exists() else cfg.embed_model
    if indexed_model != cfg.embed_model:
        raise RuntimeError(f"인덱스가 '{indexed_model}'로 생성됨 — 'horcrux reindex' 실행 필요")
    entries = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    if not entries:
        return []
    vecs = np.load(d / "embeddings.npy")

    def matches(e: dict) -> bool:
        checks = []
        if equipment:
            checks.append(bool(set(equipment) & set(e["equipment"])))
        if materials:
            checks.append(bool(set(materials) & set(e["materials"])))
        if symptom:
            checks.append(e["symptom_category"] == symptom)
        return any(checks) if checks else True

    idx = [i for i, e in enumerate(entries) if matches(e)] or list(range(len(entries)))
    q = embed(cfg, [query])[0]
    scores = vecs[idx] @ q
    order = np.argsort(scores)[::-1][:top_k]
    return [{**entries[idx[i]], "score": float(scores[i])} for i in order]
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_indexer.py tests/test_embeddings.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add src/horcrux/embeddings.py src/horcrux/indexer.py tests/test_embeddings.py tests/test_indexer.py
git commit -m "feat: 임베딩 어댑터 + 벡터 검색 인덱서 (vector 모드용)"
```

---

### Task 3.5: 검색 디스패처 (retrieval) — LLM-select + 자동 전환

**Files:**
- Create: `src/horcrux/retrieval.py`
- Test: `tests/test_retrieval.py`

**Interfaces:**
- Consumes: `indexer.search/build_index`, `llm.generate_parsed`, `records.list_records/load_record`, `config.Config`
- Produces: `effective_mode(cfg) -> str` ("llm"|"vector"); `retrieve(cfg, query, equipment=None, materials=None, symptom=None, top_k=3) -> list[dict]` — indexer.search와 동일 형태(단 llm 모드는 `score=None`, 필터 인자는 llm 모드에서 무시 — 질의 원문에 이미 포함); `maybe_reindex(cfg) -> None` (vector 모드일 때만 build_index); `SelectedCases` (pydantic: `ids: list[str]`)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_retrieval.py`

```python
from horcrux import retrieval as rt
from horcrux.config import Config
from horcrux.records import ExperimentRecord, Symptom, save_record


def make_vault(tmp_path, n=2):
    for i in range(n):
        rec = ExperimentRecord(
            id=f"2026-07-19_exp-{i:03d}", date="2026-07-19", experiment_type="스퍼터 증착",
            equipment=["RF 스퍼터"], symptom=Symptom(category="low_value", description="낮음"),
        )
        save_record(tmp_path, rec, f"원문 {i}", f"정리 {i}")
    return tmp_path


def test_effective_mode_auto_threshold(tmp_path):
    make_vault(tmp_path, 2)
    assert rt.effective_mode(Config(vault=tmp_path, search_mode="auto", search_threshold=2)) == "llm"
    assert rt.effective_mode(Config(vault=tmp_path, search_mode="auto", search_threshold=1)) == "vector"


def test_effective_mode_forced(tmp_path):
    make_vault(tmp_path, 1)
    assert rt.effective_mode(Config(vault=tmp_path, search_mode="llm")) == "llm"
    assert rt.effective_mode(Config(vault=tmp_path, search_mode="vector")) == "vector"


def test_retrieve_llm_select(tmp_path, monkeypatch):
    make_vault(tmp_path, 3)
    captured = {}

    def fake_parsed(cfg, system, user, schema):
        captured["user"] = user
        return rt.SelectedCases(ids=["2026-07-19_exp-001", "없는-id"])

    monkeypatch.setattr(rt, "generate_parsed", fake_parsed)
    hits = rt.retrieve(Config(vault=tmp_path, search_mode="llm"), "증착률 낮음")
    assert [h["id"] for h in hits] == ["2026-07-19_exp-001"]  # 카탈로그에 없는 id는 무시
    assert hits[0]["score"] is None
    assert "2026-07-19_exp-000" in captured["user"]  # 전체 레코드가 카탈로그에 포함


def test_retrieve_vector_dispatch(tmp_path, monkeypatch):
    make_vault(tmp_path, 1)
    monkeypatch.setattr(rt, "vector_search", lambda cfg, q, **kw: [{"id": "v", "score": 1.0}])
    hits = rt.retrieve(Config(vault=tmp_path, search_mode="vector"), "질의")
    assert hits[0]["id"] == "v"


def test_maybe_reindex_noop_in_llm_mode(tmp_path, monkeypatch):
    make_vault(tmp_path, 1)
    called = {}
    monkeypatch.setattr(rt, "build_index", lambda cfg: called.setdefault("x", True))
    rt.maybe_reindex(Config(vault=tmp_path, search_mode="llm"))
    assert not called
    rt.maybe_reindex(Config(vault=tmp_path, search_mode="vector"))
    assert called
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_retrieval.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `src/horcrux/retrieval.py`

```python
from __future__ import annotations

from pydantic import BaseModel, Field

from .config import Config
from .indexer import build_index
from .indexer import search as vector_search
from .llm import generate_parsed
from .records import list_records, load_record

SELECT_SYSTEM = """연구실 실험 레코드 카탈로그에서 질의와 가장 유사한 사례를 고르라.
유사 기준: 같은 장비/재료/실험 유형에서 비슷한 증상이 나타난 사례 우선.
관련 있는 것만 최대 top_k개, 유사한 것이 없으면 빈 목록. 카탈로그에 없는 id를 지어내지 마라."""


class SelectedCases(BaseModel):
    ids: list[str] = Field(default_factory=list)


def effective_mode(cfg: Config) -> str:
    if cfg.search_mode in ("llm", "vector"):
        return cfg.search_mode
    # ponytail: auto = 레코드 수 기준 단순 전환 — 수백 건 넘으면 vector로
    return "llm" if len(list_records(cfg.vault)) <= cfg.search_threshold else "vector"


def _catalog(cfg: Config) -> tuple[str, dict[str, str]]:
    lines, paths = [], {}
    for path in list_records(cfg.vault):
        rec, _ = load_record(path)
        paths[rec.id] = str(path)
        lines.append(
            f"- {rec.id} | {rec.experiment_type} | 장비: {', '.join(rec.equipment) or '-'} | "
            f"재료: {', '.join(rec.materials) or '-'} | 증상: {rec.symptom.category} {rec.symptom.description} | "
            f"결과: {rec.results[:80]}"
        )
    return "\n".join(lines), paths


def retrieve(
    cfg: Config, query: str,
    equipment: list[str] | None = None,
    materials: list[str] | None = None,
    symptom: str | None = None,
    top_k: int = 3,
) -> list[dict]:
    if effective_mode(cfg) == "vector":
        return vector_search(cfg, query, equipment=equipment, materials=materials,
                             symptom=symptom, top_k=top_k)
    catalog, paths = _catalog(cfg)
    if not catalog:
        return []
    user = f"## 질의\n{query}\n\n## top_k\n{top_k}\n\n## 카탈로그\n{catalog}"
    selected = generate_parsed(cfg, SELECT_SYSTEM, user, SelectedCases)
    return [{"id": rid, "path": paths[rid], "score": None}
            for rid in selected.ids[:top_k] if rid in paths]


def maybe_reindex(cfg: Config) -> None:
    if effective_mode(cfg) == "vector":
        build_index(cfg)
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_retrieval.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add src/horcrux/retrieval.py tests/test_retrieval.py
git commit -m "feat: 검색 디스패처 — LLM-select 기본, 임계값 초과 시 벡터 자동 전환"
```

---

### Task 4: ingest — 로그 파싱·재질문 로직

**Files:**
- Create: `src/horcrux/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `llm.generate_parsed`, `records.*`, `retrieval.maybe_reindex`, `config.Config/VaultConfig/load_vault_config`
- Produces: `ParsedLog` (pydantic: ExperimentRecord의 내용 필드 + `summary: str` + `unrecorded_required_parameters: list[str]`); `parse_log(cfg, text, vcfg: VaultConfig | None = None) -> ParsedLog` (1회 재시도 + LLM 미기재 보고를 설정 목록과 대조해 환각 이름 제거); `missing_required(p: ParsedLog, vcfg: VaultConfig) -> list[str]` (§2a 게이트 판정 — 순수 함수, 질문 문자열 목록); `FIELD_QUESTIONS: dict[str, str]`; `to_record(vault, p: ParsedLog, date: str) -> ExperimentRecord`; `read_multiline() -> str`; `run_log(cfg) -> Path | None` (대화형 전체 플로우)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_ingest.py`

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `src/horcrux/ingest.py`

```python
from __future__ import annotations

from datetime import date as _date
from pathlib import Path

from pydantic import BaseModel, Field

from .config import Config, VaultConfig, load_vault_config
from .llm import generate_parsed
from .records import (
    ExperimentRecord, Parameter, SuspectedCause, Symptom,
    make_record_id, save_record,
)
from .retrieval import maybe_reindex

PARSE_SYSTEM = """당신은 wet lab 실험 로그를 구조화하는 조수다.
연구원이 쓴 자연어 실험 로그에서 다음을 추출하라:
- experiment_type: 실험 유형 (자유 텍스트, 짧게. 예: 박막 증착, 졸겔 합성)
- objective: 실험 목적
- equipment / materials: 사용한 장비·재료 이름 목록
- parameters: 공정변수. 연구원이 통제 가능한 변수는 controllable=true, 통제 불가(습도 등 환경)는 false
- results: 결과 요약 (수치 포함)
- symptom: 문제 증상 분류 — low_value(값이 낮음), unstable(불안정/재현성 문제), abnormal(비정상 개형/거동), none(문제 없음)
- suspected_causes: 로그에 언급된 추측 원인 (전부 status=unconfirmed)
- actions_taken: 취한 조치
- summary: 로그를 2~4문장으로 정리한 서술
- unrecorded_required_parameters: 사용자 메시지에 [연구실 필수 파라미터 목록]이 있으면, 각 항목이
  로그에 기재됐는지 판단해 미기재 항목명만 목록의 표기 그대로 나열하라. 표현이 달라도 의미가 같으면
  기재된 것으로 본다 (예: 목록의 "챔버 습도" ↔ 로그의 "습도 40%"). 목록이 없으면 빈 목록.
문제가 없었다고 명시된 로그는 symptom을 category=none, description="문제 없음"으로 기록하라.
로그에 없는 내용을 지어내지 마라. 없는 필드는 비워 두라."""


class ParsedLog(BaseModel):
    experiment_type: str = ""
    objective: str = ""
    equipment: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    results: str = ""
    symptom: Symptom = Field(default_factory=Symptom)
    suspected_causes: list[SuspectedCause] = Field(default_factory=list)
    actions_taken: list[str] = Field(default_factory=list)
    summary: str = ""
    unrecorded_required_parameters: list[str] = Field(default_factory=list)


def parse_log(cfg: Config, text: str, vcfg: VaultConfig | None = None) -> ParsedLog:
    vcfg = vcfg or load_vault_config(cfg.vault)
    user = text
    if vcfg.required_parameters:
        req = "\n".join(f"- {n}" for n in vcfg.required_parameters)
        user = f"{text}\n\n[연구실 필수 파라미터 목록]\n{req}"
    try:
        p = generate_parsed(cfg, PARSE_SYSTEM, user, ParsedLog)
    except Exception:
        p = generate_parsed(cfg, PARSE_SYSTEM, user, ParsedLog)  # 1회 재시도
    # §2a — 의미 매칭은 LLM, 게이트 판단은 코드: 보고를 설정 목록과 대조, 목록 밖 이름(환각)은 무시
    p.unrecorded_required_parameters = [
        n for n in p.unrecorded_required_parameters if n in vcfg.required_parameters
    ]
    return p


FIELD_QUESTIONS = {
    "objective": "실험 목적이 무엇인가요?",
    "parameters": "설정한 공정변수(값 포함)는 무엇인가요? 이번에 변경한 변수가 있다면 함께 알려주세요.",
    "results": "실험 결과는 어땠나요?",
    "symptom": "문제나 이상 증상이 있었나요? 없었다면 '문제 없음'이라고 알려주세요.",
    "actions_taken": "문제에 대해 어떤 조치를 취했나요?",
}


def missing_required(p: ParsedLog, vcfg: VaultConfig) -> list[str]:
    filled = {
        "objective": bool(p.objective.strip()),
        "parameters": bool(p.parameters),
        "results": bool(p.results.strip()),
        "symptom": p.symptom.category != "none" or bool(p.symptom.description.strip()),
        "actions_taken": bool(p.actions_taken) or p.symptom.category == "none",
    }
    gaps = [FIELD_QUESTIONS[f] for f in vcfg.required_fields if f in filled and not filled[f]]
    gaps += [f"연구실 필수 항목 '{n}' 값을 알려주세요." for n in p.unrecorded_required_parameters]
    return gaps


def to_record(vault: Path, p: ParsedLog, date: str) -> ExperimentRecord:
    rid = make_record_id(vault, date, p.experiment_type or "exp")
    return ExperimentRecord(id=rid, date=date, **p.model_dump(exclude={"summary"}))


def read_multiline() -> str:
    lines, empty = [], 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            empty += 1
            if empty >= 2:
                break
        else:
            empty = 0
        lines.append(line)
    return "\n".join(lines).strip()


def run_log(cfg: Config) -> Path | None:
    print("실험 로그를 자연어로 입력하세요. (입력 종료: 빈 줄 2번)")
    text = read_multiline()
    if not text:
        print("입력이 없습니다.")
        return None
    today = _date.today().isoformat()
    vcfg = load_vault_config(cfg.vault)
    try:
        parsed = parse_log(cfg, text, vcfg)
    except Exception as e:
        # 파싱 실패해도 원문은 보존
        rec = ExperimentRecord(id=make_record_id(cfg.vault, today, "exp"), date=today, needs_review=True)
        path = save_record(cfg.vault, rec, text, f"(자동 파싱 실패: {e})")
        print(f"파싱에 실패해 원문만 저장했습니다 (needs_review): {path}")
        return path
    for _ in range(3):
        gaps = missing_required(parsed, vcfg)
        if not gaps:
            break
        print("\n기록 품질을 위해 추가로 알려주세요 (건너뛰려면 빈 줄 2번):")
        for q in gaps:
            print(f"  - {q}")
        extra = read_multiline()
        if not extra:
            break
        text = f"{text}\n\n[추가 답변]\n{extra}"
        parsed = parse_log(cfg, text, vcfg)
    rec = to_record(cfg.vault, parsed, today)
    path = save_record(cfg.vault, rec, text, parsed.summary)
    maybe_reindex(cfg)
    print(f"\n저장됨: {path}")
    if missing_required(parsed, vcfg):
        print("(일부 필수 정보가 비어 있는 채로 저장됨)")
    return path
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_ingest.py -v`
Expected: 10 passed

- [ ] **Step 5: 커밋**

```bash
git add src/horcrux/ingest.py tests/test_ingest.py
git commit -m "feat: 로그 LLM 파싱 + 필수 필드 재질문 루프"
```

---

### Task 5: CLI 골격 + log/reindex

**Files:**
- Create: `src/horcrux/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `ingest.run_log`, `indexer.build_index`, `config.load_config`
- Produces: `main(argv=None)` — argparse 서브커맨드 `log | ask | absorb | feedback | reindex | seed`. ask/absorb/feedback/seed는 함수 내 지연 임포트로 연결 (해당 모듈은 Task 6~9에서 생김 — 이 태스크 시점에 그 서브커맨드를 실행하면 ImportError가 나는 것이 의도된 상태)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_cli.py`

```python
import pytest

from horcrux import cli


def test_reindex_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("HORCRUX_VAULT", str(tmp_path))
    called = {}
    monkeypatch.setattr(cli, "build_index", lambda cfg: called.setdefault("n", 0))
    cli.main(["reindex"])
    assert "n" in called


def test_unknown_command_exits():
    with pytest.raises(SystemExit):
        cli.main(["nope"])
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `src/horcrux/cli.py`

```python
from __future__ import annotations

import argparse
import sys

from .config import load_config
from .indexer import build_index
from .ingest import run_log


def _utf8_console():
    for stream in (sys.stdout, sys.stdin, sys.stderr):
        try:
            if stream.encoding and stream.encoding.lower() != "utf-8":
                stream.reconfigure(encoding="utf-8")
        except Exception:
            pass  # 콘솔 인코딩 조정 실패는 치명적이지 않음


def main(argv: list[str] | None = None) -> None:
    _utf8_console()
    p = argparse.ArgumentParser(prog="horcrux", description="연구실 실험 기록·문제 진단 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("log", help="실험 로그 기록")
    sub.add_parser("ask", help="문제 질의")
    sub.add_parser("absorb", help="위키 아티클 편찬")
    sub.add_parser("reindex", help="검색 인덱스 재생성")
    fb = sub.add_parser("feedback", help="해결 여부·실제 원인 기록")
    fb.add_argument("record_id")
    fb.add_argument("--resolved", choices=["y", "n"], required=True)
    fb.add_argument("--cause", default=None, help="확인된 실제 원인")
    fb.add_argument("--note", default="")
    sd = sub.add_parser("seed", help="합성 데모 데이터 생성")
    sd.add_argument("-n", type=int, default=6)
    args = p.parse_args(argv)
    cfg = load_config()

    if args.cmd == "log":
        run_log(cfg)
    elif args.cmd == "reindex":
        n = build_index(cfg)
        print(f"인덱스 재생성: {n}건")
    elif args.cmd == "ask":
        from .diagnose import run_ask
        run_ask(cfg)
    elif args.cmd == "feedback":
        from .feedback import run_feedback
        run_feedback(cfg, args.record_id, args.resolved == "y", args.cause, args.note)
    elif args.cmd == "absorb":
        from .absorb import run_absorb
        n = run_absorb(cfg)
        print(f"아티클 갱신: {n}건")
    elif args.cmd == "seed":
        from .seed import run_seed
        run_seed(cfg, args.n)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_cli.py -v`
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add src/horcrux/cli.py tests/test_cli.py
git commit -m "feat: horcrux CLI 골격 (log/reindex 연결)"
```

---

### Task 6: diagnose — 질의 구조화·증상 분기·응답 생성

**Files:**
- Create: `src/horcrux/diagnose.py`
- Test: `tests/test_diagnose.py`

**Interfaces:**
- Consumes: `llm.generate/generate_parsed`, `retrieval.retrieve`, `ingest.read_multiline`, `records.read_md/slugify/Symptom`. 위키 경로는 이 모듈에서 `vault / "wiki"`로 직접 계산 (absorb는 Task 8에서 같은 규약 사용)
- Produces: `QueryInfo` (pydantic: `experiment_type, equipment, materials, changed_variables, symptom`); `structure_query(cfg, text) -> QueryInfo`; `missing_min_info(q) -> list[str]`; `diagnose(cfg, text, q) -> str` (순수 분기: abnormal→`ESCALATION` 상수 반환, 그 외→검색+생성); `ESCALATION: str`; `run_ask(cfg)` (대화형)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_diagnose.py`

```python
from horcrux import diagnose as dg
from horcrux.config import Config
from horcrux.diagnose import ESCALATION, QueryInfo, diagnose, missing_min_info
from horcrux.records import Symptom


def test_missing_min_info_empty():
    gaps = missing_min_info(QueryInfo())
    assert len(gaps) == 2  # 증상 설명 + 실험/장비


def test_missing_min_info_satisfied():
    q = QueryInfo(equipment=["RF 스퍼터"], symptom=Symptom(category="low_value", description="증착률 낮음"))
    assert missing_min_info(q) == []


def test_abnormal_branch_escalates_without_llm(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("abnormal 분기에서 LLM/검색을 호출하면 안 됨")

    monkeypatch.setattr(dg, "generate", boom)
    monkeypatch.setattr(dg, "retrieve", boom)
    q = QueryInfo(equipment=["X"], symptom=Symptom(category="abnormal", description="개형이 이상함"))
    assert diagnose(Config(vault="v"), "질문", q) == ESCALATION


def test_normal_branch_uses_search_and_generate(tmp_path, monkeypatch):
    from horcrux.records import ExperimentRecord, save_record

    rec = ExperimentRecord(id="2026-07-19_sputter-001", date="2026-07-19",
                           equipment=["RF 스퍼터"], experiment_type="스퍼터 증착")
    path = save_record(tmp_path, rec, "원문", "정리")
    monkeypatch.setattr(dg, "retrieve", lambda cfg, q, **kw: [
        {"id": rec.id, "path": str(path), "score": 0.9},
    ])
    captured = {}

    def fake_generate(cfg, system, user):
        captured["user"] = user
        return "진단 응답"

    monkeypatch.setattr(dg, "generate", fake_generate)
    q = QueryInfo(equipment=["RF 스퍼터"], symptom=Symptom(category="low_value", description="증착률 낮음"))
    out = diagnose(Config(vault=tmp_path), "증착률이 낮아요", q)
    assert out == "진단 응답"
    assert "2026-07-19_sputter-001" in captured["user"]  # 사례가 컨텍스트에 포함됨


def test_no_cases_labelled_general(monkeypatch, tmp_path):
    monkeypatch.setattr(dg, "retrieve", lambda cfg, q, **kw: [])
    monkeypatch.setattr(dg, "generate", lambda cfg, s, u: "일반 지식 응답")
    q = QueryInfo(equipment=["X"], symptom=Symptom(category="unstable", description="불안정"))
    out = diagnose(Config(vault=tmp_path), "질문", q)
    assert "축적된 유사 사례가 없" in out
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_diagnose.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `src/horcrux/diagnose.py`

```python
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .config import Config
from .ingest import read_multiline
from .llm import generate, generate_parsed
from .records import Symptom, read_md, slugify
from .retrieval import retrieve

QUERY_SYSTEM = """연구원의 실험 문제 질의를 구조화하라.
- experiment_type / equipment / materials: 질의에 언급된 것
- changed_variables: 이번 실험에서 변경했다고 언급된 변수
- symptom: category 분류 — low_value(값이 낮음), unstable(불안정/재현성), abnormal(비정상 개형/거동), none(불명) + description(증상 설명)
질의에 없는 내용을 지어내지 마라."""


class QueryInfo(BaseModel):
    experiment_type: str = ""
    equipment: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    changed_variables: list[str] = Field(default_factory=list)
    symptom: Symptom = Field(default_factory=Symptom)


ESCALATION = (
    "증상이 '비정상 개형'으로 분류됩니다. 과거 사례 매칭보다 실험 설계 자체의 문제일 가능성이 있어, "
    "AI가 원인을 단정하지 않습니다. 지도교수/선배 연구자와 상의하세요.\n"
    "상의 전 준비하면 좋은 것: 원본 데이터(그래프), 변경한 변수 목록, 장비 설정/캘리브레이션 기록."
)

ANSWER_SYSTEM = """당신은 연구실의 과거 실험 기록을 근거로 문제 진단을 보조하는 조수다.
제공된 유사 사례와 위키 아티클만 근거로 다음 구성으로 답하라:
1) 유사 사례 요약 (반드시 레코드 id 인용)
2) 원인 후보 (과거에 확인된(confirmed) 원인 우선, 미확정(unconfirmed) 추측은 그렇다고 명시)
3) 확인 방법 (무엇을 먼저 확인할지 순서대로)
컨텍스트에 없는 사례를 지어내지 마라. 사례가 없다고 표시된 경우, 일반 지식 기반 조언임을 명확히 밝혀라."""


def structure_query(cfg: Config, text: str) -> QueryInfo:
    return generate_parsed(cfg, QUERY_SYSTEM, text, QueryInfo)


def missing_min_info(q: QueryInfo) -> list[str]:
    gaps = []
    if not q.symptom.description.strip():
        gaps.append("어떤 증상인가요? (예: 값이 낮다 / 들쭉날쭉하다 / 개형이 이상하다)")
    if not q.equipment and not q.experiment_type.strip():
        gaps.append("어떤 실험 또는 장비에서 발생했나요?")
    return gaps


def _wiki_context(vault: Path, q: QueryInfo) -> str:
    parts = []
    wiki = vault / "wiki"
    names = [("equipment", n) for n in q.equipment] + [("materials", n) for n in q.materials]
    for kind, name in names:
        p = wiki / kind / f"{slugify(name)}.md"
        if p.exists():
            parts.append(f"### 위키/{kind}/{name}\n{p.read_text(encoding='utf-8')}")
    fm_dir = wiki / "failure-modes"
    if fm_dir.exists():
        for p in sorted(fm_dir.glob("*.md")):
            meta, body = read_md(p)
            if (meta or {}).get("symptom_category") == q.symptom.category:
                parts.append(f"### 위키/failure-modes/{p.stem}\n{body}")
    return "\n\n".join(parts)


def diagnose(cfg: Config, text: str, q: QueryInfo) -> str:
    if q.symptom.category == "abnormal":
        return ESCALATION
    symptom = q.symptom.category if q.symptom.category in ("low_value", "unstable") else None
    hits = retrieve(cfg, text, equipment=q.equipment or None,
                    materials=q.materials or None, symptom=symptom)
    case_parts = []
    for h in hits:
        tag = f"(유사도 {h['score']:.2f})" if h.get("score") is not None else "(LLM 선정)"
        case_parts.append(f"### 사례 {h['id']} {tag}\n"
                          + Path(h["path"]).read_text(encoding="utf-8"))
    cases = "\n\n".join(case_parts) if case_parts else "(축적된 유사 사례 없음)"
    wiki = _wiki_context(cfg.vault, q)
    user = (f"## 질의\n{text}\n\n## 구조화된 질의\n{q.model_dump_json()}\n\n"
            f"## 유사 사례\n{cases}\n\n## 위키 아티클\n{wiki or '(없음)'}")
    answer = generate(cfg, ANSWER_SYSTEM, user)
    if not hits:
        answer = "⚠ 아직 축적된 유사 사례가 없습니다. 아래는 일반 지식 기반 조언입니다.\n\n" + answer
    return answer


def run_ask(cfg: Config) -> None:
    print("문제 상황을 설명해주세요. (입력 종료: 빈 줄 2번)")
    text = read_multiline()
    if not text:
        print("입력이 없습니다.")
        return
    q = structure_query(cfg, text)
    for _ in range(3):
        gaps = missing_min_info(q)
        if not gaps:
            break
        print("\n진단을 위해 추가로 알려주세요 (건너뛰려면 빈 줄 2번):")
        for g in gaps:
            print(f"  - {g}")
        extra = read_multiline()
        if not extra:
            break
        text = f"{text}\n\n[추가 답변]\n{extra}"
        q = structure_query(cfg, text)
    print("\n" + diagnose(cfg, text, q))
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_diagnose.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add src/horcrux/diagnose.py tests/test_diagnose.py
git commit -m "feat: 문제 질의 구조화 + 증상 분기 진단 (abnormal은 사람 연결)"
```

---

### Task 7: feedback — 결과 피드백 → DB 갱신

**Files:**
- Create: `src/horcrux/feedback.py`
- Test: `tests/test_feedback.py`

**Interfaces:**
- Consumes: `records.update_resolution/record_path`, `retrieval.maybe_reindex`
- Produces: `run_feedback(cfg, record_id: str, resolved: bool, cause: str | None, note: str) -> None`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_feedback.py`

```python
from horcrux import feedback as fb
from horcrux.config import Config
from horcrux.records import ExperimentRecord, SuspectedCause, load_record, record_path, save_record


def test_run_feedback_updates_and_reindexes(tmp_path, monkeypatch):
    rec = ExperimentRecord(id="2026-07-19_x-001", date="2026-07-19",
                           suspected_causes=[SuspectedCause(cause="타겟 산화")])
    save_record(tmp_path, rec, "원문", "정리")
    reindexed = {}
    monkeypatch.setattr(fb, "maybe_reindex", lambda cfg: reindexed.setdefault("ok", True))
    fb.run_feedback(Config(vault=tmp_path), rec.id, True, "타겟 산화", "연마 후 해결")
    loaded, _ = load_record(record_path(tmp_path, rec.id))
    assert loaded.resolution.resolved is True
    assert loaded.resolution.actual_cause == "타겟 산화"
    assert loaded.suspected_causes[0].status == "confirmed"
    assert reindexed.get("ok")


def test_run_feedback_missing_record(tmp_path, capsys):
    fb.run_feedback(Config(vault=tmp_path), "없는-id", True, None, "")
    assert "찾을 수 없음" in capsys.readouterr().out
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_feedback.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `src/horcrux/feedback.py`

```python
from __future__ import annotations

from .config import Config
from .records import record_path, update_resolution
from .retrieval import maybe_reindex


def run_feedback(cfg: Config, record_id: str, resolved: bool, cause: str | None, note: str) -> None:
    if not record_path(cfg.vault, record_id).exists():
        print(f"레코드를 찾을 수 없음: {record_id}")
        return
    rec = update_resolution(cfg.vault, record_id, resolved, cause, note)
    maybe_reindex(cfg)
    state = "해결" if resolved else "미해결"
    print(f"{rec.id}: {state}로 기록됨" + (f" (원인: {cause})" if cause else ""))
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_feedback.py -v`
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add src/horcrux/feedback.py tests/test_feedback.py
git commit -m "feat: 피드백으로 해결 여부·실제 원인 갱신"
```

---

### Task 8: absorb — 위키 아티클 편찬

**Files:**
- Create: `src/horcrux/absorb.py`
- Test: `tests/test_absorb.py`

**Interfaces:**
- Consumes: `llm.generate`, `records.list_records/load_record/read_md/write_md/slugify/ExperimentRecord`
- Produces: `run_absorb(cfg) -> int` (갱신된 아티클 수); `group_targets(records: list[ExperimentRecord]) -> dict[tuple[str, str], list[str]]` (키=(kind, name), kind∈{equipment, materials, failure-modes}, 값=record id 목록 — 순수 함수); `CATEGORY_KO: dict`; `wiki_dir(vault) -> Path`. **한 번 흡수된 레코드는 다시 편찬하지 않는다** (ponytail: feedback 갱신 재반영은 `wiki/_absorb_log.json` 삭제 후 재실행으로 대체, 필요해지면 해시 비교 추가)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_absorb.py`

```python
import json

from horcrux import absorb as ab
from horcrux.config import Config
from horcrux.records import ExperimentRecord, Symptom, save_record


def make_rec(tmp_path, rid, equipment, category="low_value"):
    rec = ExperimentRecord(id=rid, date="2026-07-19", experiment_type="스퍼터 증착",
                           equipment=equipment, materials=["ITO 타겟"],
                           symptom=Symptom(category=category, description="문제"))
    save_record(tmp_path, rec, "원문", "정리")
    return rec


def test_group_targets():
    r = ExperimentRecord(id="a", date="d", experiment_type="스퍼터 증착",
                         equipment=["RF 스퍼터"], materials=["ITO 타겟"],
                         symptom=Symptom(category="low_value", description="x"))
    groups = ab.group_targets([r])
    assert ("equipment", "RF 스퍼터") in groups
    assert ("materials", "ITO 타겟") in groups
    assert ("failure-modes", "스퍼터 증착-값낮음") in groups


def test_group_targets_no_failure_mode_when_none():
    r = ExperimentRecord(id="a", date="d", equipment=["X"], symptom=Symptom(category="none"))
    groups = ab.group_targets([r])
    assert not any(k[0] == "failure-modes" for k in groups)


def test_absorb_writes_articles_and_is_idempotent(tmp_path, monkeypatch):
    calls = []

    def fake_generate(cfg, system, user):
        calls.append(user)
        return "아티클 본문"

    monkeypatch.setattr(ab, "generate", fake_generate)
    cfg = Config(vault=tmp_path)
    make_rec(tmp_path, "2026-07-19_sputter-001", ["RF 스퍼터"])
    n1 = ab.run_absorb(cfg)
    assert n1 == 3  # equipment 1 + materials 1 + failure-mode 1
    assert (tmp_path / "wiki" / "equipment" / "rf-스퍼터.md").exists()
    log = json.loads((tmp_path / "wiki" / "_absorb_log.json").read_text(encoding="utf-8"))
    assert "2026-07-19_sputter-001" in log
    # 두 번째 실행: 신규 레코드 없음 → 아무것도 안 함
    n2 = ab.run_absorb(cfg)
    assert n2 == 0
    assert len(calls) == 3


def test_absorb_updates_existing_article(tmp_path, monkeypatch):
    captured = []

    def fake_generate(cfg, system, user):
        captured.append(user)
        return "갱신된 아티클"

    monkeypatch.setattr(ab, "generate", fake_generate)
    cfg = Config(vault=tmp_path)
    make_rec(tmp_path, "2026-07-19_sputter-001", ["RF 스퍼터"])
    ab.run_absorb(cfg)
    captured.clear()
    make_rec(tmp_path, "2026-07-19_sputter-002", ["RF 스퍼터"])
    ab.run_absorb(cfg)
    # 기존 아티클 본문이 갱신 프롬프트에 포함되어야 함
    assert any("갱신된 아티클" in u for u in captured)
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_absorb.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `src/horcrux/absorb.py`

```python
from __future__ import annotations

import json
from datetime import date as _date
from pathlib import Path

from .config import Config
from .llm import generate
from .records import ExperimentRecord, list_records, load_record, read_md, slugify, write_md

CATEGORY_KO = {"low_value": "값낮음", "unstable": "불안정", "abnormal": "비정상"}

ARTICLE_SYSTEM = """연구실 위키 아티클을 편찬한다. 한국어, 위키피디아 톤(과장·1인칭·편집자 목소리 금지).
아티클 종류별 내용:
- equipment: 해당 장비의 운용 노하우, 자주 발생한 문제와 해결 이력
- materials: 해당 재료의 취급 노하우, 관련 문제
- failure-modes: 해당 실패 모드의 과거 사례, 원인 분포(확인된 원인 vs 미확정 추측 구분), 확인 순서
기존 아티클이 주어지면 새 사례를 통합해 전체를 다시 쓰고, 없으면 새로 작성한다.
사례를 언급할 때 반드시 레코드 id를 남겨라. 레코드에 없는 내용을 지어내지 마라.
출력은 아티클 본문 마크다운만 (frontmatter 없이)."""


def wiki_dir(vault: Path) -> Path:
    return vault / "wiki"


def _absorb_log_path(vault: Path) -> Path:
    return wiki_dir(vault) / "_absorb_log.json"


def _load_log(vault: Path) -> dict:
    p = _absorb_log_path(vault)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def group_targets(records: list[ExperimentRecord]) -> dict[tuple[str, str], list[str]]:
    groups: dict[tuple[str, str], list[str]] = {}
    for rec in records:
        for e in rec.equipment:
            groups.setdefault(("equipment", e), []).append(rec.id)
        for m in rec.materials:
            groups.setdefault(("materials", m), []).append(rec.id)
        if rec.symptom.category in CATEGORY_KO:
            name = f"{rec.experiment_type or '일반'}-{CATEGORY_KO[rec.symptom.category]}"
            groups.setdefault(("failure-modes", name), []).append(rec.id)
    return groups


def _rebuild_index_md(vault: Path) -> None:
    lines = ["# 위키 색인", ""]
    for kind in ("equipment", "materials", "failure-modes"):
        d = wiki_dir(vault) / kind
        articles = sorted(d.glob("*.md")) if d.exists() else []
        if articles:
            lines.append(f"## {kind}")
            lines += [f"- [[{kind}/{p.stem}]]" for p in articles]
            lines.append("")
    (wiki_dir(vault) / "_index.md").write_text("\n".join(lines), encoding="utf-8")


def run_absorb(cfg: Config) -> int:
    log = _load_log(cfg.vault)
    new: list[ExperimentRecord] = []
    texts_by_id: dict[str, str] = {}
    for path in list_records(cfg.vault):
        rec, _ = load_record(path)
        texts_by_id[rec.id] = path.read_text(encoding="utf-8")
        if rec.id not in log:
            new.append(rec)
    if not new:
        return 0
    groups = group_targets(new)
    updated = 0
    today = _date.today().isoformat()
    for (kind, name), rec_ids in groups.items():
        art_path = wiki_dir(cfg.vault) / kind / f"{slugify(name)}.md"
        existing_meta, existing_body = ({}, "")
        if art_path.exists():
            existing_meta, existing_body = read_md(art_path)
        cases = "\n\n---\n\n".join(texts_by_id[rid] for rid in rec_ids)
        user = (f"아티클 종류: {kind}\n아티클 이름: {name}\n\n"
                f"## 기존 아티클\n{existing_body or '(없음)'}\n\n## 새 사례\n{cases}")
        body = generate(cfg, ARTICLE_SYSTEM, user)
        meta = {"name": name, "kind": kind, "updated": today,
                "records": sorted(set((existing_meta or {}).get("records", []) + rec_ids))}
        if kind == "failure-modes":
            cat = next(r.symptom.category for r in new if r.id in rec_ids)
            meta["symptom_category"] = cat
        write_md(art_path, meta, body)
        updated += 1
    for rec in new:
        log[rec.id] = True
    _absorb_log_path(cfg.vault).parent.mkdir(parents=True, exist_ok=True)
    _absorb_log_path(cfg.vault).write_text(
        json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    _rebuild_index_md(cfg.vault)
    return updated
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_absorb.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/horcrux/absorb.py tests/test_absorb.py
git commit -m "feat: 위키 편찬 absorb (장비/재료/실패모드, 멱등)"
```

---

### Task 9: seed + README + E2E 스모크

**Files:**
- Create: `src/horcrux/seed.py`
- Create: `README.md`
- Test: `tests/test_seed.py`

**Interfaces:**
- Consumes: `llm.generate_parsed`, `ingest.parse_log/to_record` (모듈 별칭 `ingest_mod`로 임포트 — 테스트에서 monkeypatch 대상), `records.save_record`, `retrieval.maybe_reindex`
- Produces: `SeedBatch` (pydantic: `logs: list[str]`); `run_seed(cfg, n: int) -> int`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_seed.py`

```python
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
    monkeypatch.setattr(sd, "maybe_reindex", lambda cfg: None)
    cfg = Config(vault=tmp_path)
    n = sd.run_seed(cfg, 2)
    assert n == 2
    assert len(list_records(tmp_path)) == 2
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_seed.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `src/horcrux/seed.py`

```python
from __future__ import annotations

from datetime import date as _date

from pydantic import BaseModel, Field

from . import ingest as ingest_mod
from .config import Config
from .llm import generate_parsed
from .records import save_record
from .retrieval import maybe_reindex

SEED_SYSTEM = """wet lab 연구실의 가상 실험 로그를 만든다.
시나리오 예: RF 스퍼터링 ITO 박막 증착, 졸겔 TiO2 합성, 전기화학 증착, 스핀코팅.
신입~중급 연구원이 실험 직후 쓴 것 같은 자연스러운 한국어 로그 (목적, 장비, 공정변수 값, 결과 포함).
일부는 성공, 일부는 문제 포함 — 값이 낮음 / 재현 안 됨 / 개형이 이상함을 골고루.
서로 다른 시나리오·조건으로 다양하게."""


class SeedBatch(BaseModel):
    logs: list[str] = Field(default_factory=list)


def run_seed(cfg: Config, n: int) -> int:
    batch = generate_parsed(cfg, SEED_SYSTEM, f"실험 로그 {n}건을 생성하라.", SeedBatch)
    today = _date.today().isoformat()
    saved = 0
    for text in batch.logs[:n]:
        parsed = ingest_mod.parse_log(cfg, text)
        rec = ingest_mod.to_record(cfg.vault, parsed, today)
        save_record(cfg.vault, rec, text, parsed.summary)
        saved += 1
    maybe_reindex(cfg)
    print(f"합성 로그 {saved}건 저장")
    return saved
```

- [ ] **Step 4: 통과 확인 + 전체 테스트**

Run: `pytest -v`
Expected: 전체 passed (API 호출·모델 다운로드 없음)

- [ ] **Step 5: README.md 작성**

````markdown
# horcrux

연구실 실험 기록·문제 진단 CLI. 실험 로그를 자연어로 입력하면 LLM이 구조화해
마크다운 볼트(옵시디언 호환)에 저장하고, 문제 질의 시 과거 유사 사례를 검색해
근거와 함께 진단을 보조한다.

## 설치

```
pip install -e .
set ANTHROPIC_API_KEY=...           # 또는 ant auth login
set HORCRUX_VAULT=example-vault     # 랩 볼트 경로 (연구실 1곳 = 볼트 1개)
```

검색은 기본 자동 모드: 레코드 200건 이하면 LLM이 카탈로그를 읽고 유사 사례를 직접 고른다
(임베딩 불필요). 넘어가면 벡터 검색으로 자동 전환 — 그때는:

```
pip install -e ".[vector]"    # sentence-transformers (로컬 임베딩, 기본 EmbeddingGemma)
horcrux reindex               # 벡터 인덱스 1회 생성
```

강제 모드: `set HORCRUX_SEARCH=llm` 또는 `vector`. 임계값: `HORCRUX_SEARCH_THRESHOLD` (기본 200).

## 사용

```
horcrux seed          # 합성 데모 데이터 생성 (개발용)
horcrux log           # 실험 로그 기록 (부족한 필수 정보는 되물음)
horcrux ask           # 문제 질의 (비정상 개형은 사람 연결 안내)
horcrux absorb        # 장비/재료/실패모드 위키 아티클 편찬
horcrux feedback <id> --resolved y --cause "타겟 산화"   # 결과 피드백
horcrux reindex       # 검색 인덱스 재생성
```

## 연구실 설정 (§2a)

볼트에 `config.yaml`을 두면 기록 시 하드 게이트가 적용된다 (없으면 5개 카테고리 전부 기본):

```
required_fields: [objective, parameters, results, symptom, actions_taken]
required_parameters:
  - 기판 온도
  - 챔버 습도
```

설계 문서: `docs/superpowers/specs/2026-07-19-horcrux-mvp-design.md`
````

- [ ] **Step 6: E2E 스모크 (실제 API, 수동 1회)**

Run (ANTHROPIC_API_KEY 필요 — 기본 llm 검색 모드라 임베딩·모델 다운로드 없음):
```bash
set HORCRUX_VAULT=example-vault
horcrux seed -n 4
horcrux absorb
horcrux ask     # 대화형: "스퍼터 증착률이 평소보다 낮아요. RF 스퍼터 썼습니다." 입력
```
Expected: seed가 `example-vault/raw/experiments/`에 md 4건 생성, absorb가 `example-vault/wiki/`에 아티클 생성, ask가 사례 id를 인용한 진단 응답 출력.

- [ ] **Step 7: 커밋**

```bash
git add src/horcrux/seed.py tests/test_seed.py README.md
git commit -m "feat: 합성 데이터 시드 + README"
git add example-vault
git commit -m "chore: 데모용 예시 볼트"
```

---

## Self-Review 결과

- **스펙 커버리지**: log/ask/absorb/feedback/reindex/seed 전 명령, 재질문 루프(최대 3회, §2a 볼트 config.yaml 하드 게이트 — required_fields 토글 + required_parameters 커스텀, 의미 매칭 LLM/게이트 판단 코드), 증상 분기(abnormal→사람 연결), 원문 보존+needs_review, 멱등 absorb, 생성 LLM·임베딩 양쪽 어댑터 격리, 검색 이중 모드(LLM-select 기본 + 임계값 초과 시 벡터 자동 전환) — 모두 태스크에 매핑됨.
- **타입 일관성**: `ParsedLog`/`QueryInfo`는 `records.py`의 `Parameter/Symptom/SuspectedCause` 재사용. `slugify`는 Task 1 정의 → Task 6·8 소비. `read_multiline`은 Task 4 정의 → Task 6 소비. `retrieval.retrieve/maybe_reindex`는 Task 3.5 정의 → Task 4·6·7·9 소비 (retrieve 반환 형태는 indexer.search와 동일, llm 모드는 score=None). `wiki_dir` 규약(`vault/"wiki"`)은 Task 6·8 동일.
- **임포트 사이클 없음**: retrieval → {indexer, llm, records}; ingest/diagnose/feedback/seed → retrieval. indexer → embeddings (sentence-transformers는 local 분기 안에서 지연 임포트라 llm 모드에선 로드 안 됨).
- **알려진 한계(의도된 단순화)**: absorb는 feedback으로 갱신된 레코드를 재편찬하지 않음(`_absorb_log.json` 삭제 후 재실행으로 대체), 인덱스는 전체 재빌드, llm 모드에서 필터 인자 무시(질의 원문으로 충분) — 코드에 ponytail 주석으로 명시.
