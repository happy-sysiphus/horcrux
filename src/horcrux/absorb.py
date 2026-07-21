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
        try:
            rec, _ = load_record(path)
        except Exception:
            print(f"(무시: 레코드 파싱 불가 — {path.name})")
            continue
        if rec.needs_review:
            continue  # 파싱 실패 원문 — 손편집 복구(needs_review 해제) 후 자연 편찬
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
