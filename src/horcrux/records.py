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
    _, fm, body = re.split(r"(?m)^---\s*$", text, maxsplit=2)
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
