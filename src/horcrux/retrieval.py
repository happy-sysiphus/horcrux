from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .config import Config
from .llm import generate_parsed
from .records import list_records, load_record

SELECT_SYSTEM = """연구실 실험 레코드·위키 카탈로그에서 질의와 관련된 항목을 고르라.
유사 기준: 같은 장비/재료/실험 유형에서 비슷한 증상이 나타난 사례 우선.
유사도가 비슷하면 원인이 확정된(해결: 표시가 있는) 사례를 우선하라.
레코드는 관련 있는 것만 최대 top_k개, 위키 아티클은 관련된 것 전부.
유사한 것이 없으면 빈 목록. 카탈로그에 없는 id를 지어내지 마라."""


class Selected(BaseModel):
    record_ids: list[str] = Field(default_factory=list)
    wiki_ids: list[str] = Field(default_factory=list)


def _wiki_articles(vault: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for kind in ("equipment", "materials", "failure-modes"):
        d = vault / "wiki" / kind
        if d.exists():
            for p in sorted(d.glob("*.md")):
                out[f"{kind}/{p.stem}"] = p
    return out


# ponytail: 카탈로그를 질의마다 전체 재구성 — 레코드 수백 건 초과로 컨텍스트가 부족해지면 벡터 검색 계층 추가
def retrieve(cfg: Config, query: str, top_k: int = 3) -> dict:
    rec_paths: dict[str, Path] = {}
    lines = []
    for path in list_records(cfg.vault):
        try:
            rec, _ = load_record(path)
        except Exception:
            print(f"(무시: 레코드 파싱 불가 — {path.name})")
            continue
        rec_paths[rec.id] = path
        if rec.symptom.category == "none":
            res_tag = "문제 없음"
        elif rec.resolution.resolved:
            res_tag = f"해결: {rec.resolution.actual_cause or '원인 미기록'}"
        else:
            res_tag = "미해결"
        notes_tag = f" | 특이사항: {rec.notes[:60]}" if rec.notes.strip() else ""
        lines.append(
            f"- {rec.id} | {rec.experiment_type} | 장비: {', '.join(rec.equipment) or '-'} | "
            f"재료: {', '.join(rec.materials) or '-'} | 증상: {rec.symptom.category} {rec.symptom.description} | "
            f"결과: {rec.results[:80]} | {res_tag}{notes_tag}"
        )
    wiki = _wiki_articles(cfg.vault)
    if not rec_paths and not wiki:
        return {"records": [], "wiki": []}
    user = (
        f"## 질의\n{query}\n\n## top_k\n{top_k}\n\n"
        "## 레코드 카탈로그\n" + ("\n".join(lines) or "(없음)") + "\n\n"
        "## 위키 아티클 목록\n" + ("\n".join(f"- {w}" for w in wiki) or "(없음)")
    )
    sel = generate_parsed(cfg, SELECT_SYSTEM, user, Selected)
    valid = [r for r in sel.record_ids if r in rec_paths][:top_k]
    return {
        "records": [{"id": r, "path": str(rec_paths[r])} for r in valid],
        "wiki": [{"id": w, "path": str(wiki[w])} for w in sel.wiki_ids if w in wiki],
    }
