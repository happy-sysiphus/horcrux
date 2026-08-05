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
- summary: 로그를 2~4문장으로 정리한 서술 (마크다운 서식 없이 평문)
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
    return ExperimentRecord(
        id=rid, date=date,
        **p.model_dump(exclude={"summary", "unrecorded_required_parameters"}),
    )


def save_unparsed(vault: Path, text: str, err: str) -> Path:
    """파싱 실패 원문을 needs_review로 보존 — CLI·봇 공용 (데이터 유실 방지)."""
    today = _date.today().isoformat()
    rec = ExperimentRecord(id=make_record_id(vault, today, "exp"), date=today, needs_review=True)
    return save_record(vault, rec, text, f"(자동 파싱 실패: {err})")


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
        path = save_unparsed(cfg.vault, text, str(e))
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
        try:
            parsed = parse_log(cfg, text, vcfg)
        except Exception:
            break  # 재파싱 실패 — 직전 파싱 결과 + 누적 원문으로 저장 진행
    rec = to_record(cfg.vault, parsed, today)
    path = save_record(cfg.vault, rec, text, parsed.summary)
    print(f"\n저장됨: {path}")
    if missing_required(parsed, vcfg):
        print("(일부 필수 정보가 비어 있는 채로 저장됨)")
    return path
