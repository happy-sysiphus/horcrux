from __future__ import annotations

import re
from pathlib import Path

from .config import Config
from .ingest import read_multiline
from .llm import generate
from .records import load_record
from .retrieval import retrieve

ANSWER_SYSTEM = """당신은 연구실의 과거 실험 기록을 근거로 문제 진단을 보조하는 조수다.
제공된 유사 사례와 위키 아티클만 근거로 다음 구성으로 답하라:
1) 유사 사례 요약 (반드시 레코드 id 인용)
2) 원인 후보 (과거에 확인된(confirmed) 원인 우선, 미확정(unconfirmed) 추측은 그렇다고 명시)
3) 확인 방법 (무엇을 먼저 확인할지 순서대로)
컨텍스트에 없는 사례를 지어내지 마라. 사례가 없다고 표시된 경우, 일반 지식 기반 조언임을 명확히 밝혀라.
마크다운 서식(**강조**, # 헤더 등) 없이 평문으로 써라. 번호·하이픈 목록만 허용."""


def _strip_md(text: str) -> str:
    # LLM이 지시를 어기고 넣은 볼드·헤더 마커 제거 — 채팅 UI에 평문으로 나가야 함
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    return re.sub(r"(?m)^#{1,6}\s+", "", text)


def diagnose_data(cfg: Config, text: str) -> dict:
    res = retrieve(cfg, text)
    cases = "\n\n".join(
        f"### 사례 {r['id']}\n" + Path(r["path"]).read_text(encoding="utf-8")
        for r in res["records"]
    ) or "(축적된 유사 사례 없음)"
    wiki = "\n\n".join(
        f"### 위키/{w['id']}\n" + Path(w["path"]).read_text(encoding="utf-8")
        for w in res["wiki"]
    ) or "(없음)"
    user = f"## 질의\n{text}\n\n## 유사 사례\n{cases}\n\n## 위키 아티클\n{wiki}"
    answer = _strip_md(generate(cfg, ANSWER_SYSTEM, user))
    if not res["records"] and not res["wiki"]:
        evidence = "none"
    elif not res["records"]:
        evidence = "wiki"
    else:
        evidence = "records"
    records_meta = []
    for r in res["records"]:
        rec, _ = load_record(Path(r["path"]))
        records_meta.append({
            "id": rec.id, "date": rec.date, "experiment_type": rec.experiment_type,
            "objective": rec.objective, "symptom": rec.symptom.model_dump(),
            "resolution": rec.resolution.model_dump(),
        })
    return {"answer": answer, "evidence": evidence,
            "records": records_meta, "wiki": [w["id"] for w in res["wiki"]]}


def diagnose(cfg: Config, text: str) -> str:
    d = diagnose_data(cfg, text)
    answer = d["answer"]
    if d["evidence"] == "none":
        answer = "⚠ 아직 축적된 유사 사례가 없습니다. 아래는 일반 지식 기반 조언입니다.\n\n" + answer
    elif d["evidence"] == "wiki":
        answer = "ℹ 직접 유사한 실험 레코드는 없어, 아래는 연구실 위키 아티클 기반 조언입니다.\n\n" + answer
    return answer


def run_ask(cfg: Config) -> None:
    print("문제 상황을 설명해주세요. 장비·재료·증상을 포함하면 더 정확합니다. (입력 종료: 빈 줄 2번)")
    text = read_multiline()
    if not text:
        print("입력이 없습니다.")
        return
    print("\n" + diagnose(cfg, text))
