# AGENTS.md — Horcrux 작업 지침

에이전트(Codex 등)가 이 저장소에서 작업할 때 따라야 할 지침이다.

## 프로젝트

**horcrux** — wet lab(재료/공정/화학) 연구실의 실험 기록·문제 진단 CLI.
연구원이 자연어로 실험 로그를 입력하면 LLM이 구조화해 마크다운 볼트(옵시디언 호환)에
저장하고, 문제 질의 시 과거 유사 사례·위키를 검색해 근거와 함께 진단을 보조한다.

- 언어/스택: Python 3.10+, pydantic v2, pyyaml, pytest (src/ 레이아웃). LLM은 로컬 CLI subprocess 호출.
- 현재 상태: **MVP 구현 완료** (Task 1~9 + 최종 리뷰 반영)

## 진실의 원천 문서

| 문서 | 역할 |
|---|---|
| `docs/superpowers/specs/2026-07-19-horcrux-mvp-design.md` | 승인된 설계 스펙 — 무엇을/왜 |
| `docs/superpowers/plans/2026-07-19-horcrux-mvp.md` | 구현 계획 — 실행 기준. Task 1~9, 태스크별 테스트·구현 코드·커밋 메시지 포함 |

이 파일(AGENTS.md)과 위 문서가 충돌하면 **스펙·계획서가 우선**한다.

## 구현 방법

- 계획서의 **Task 1 → 9 순서대로**, 태스크 안에서는 Step 순서대로 진행한다 (TDD:
  실패하는 테스트 먼저 → 실패 확인 → 구현 → 통과 확인).
- 커밋은 각 태스크 마지막 Step의 git 명령을 그대로 따른다 (Task 1~8은 커밋 1개,
  Task 9는 2개 — seed/README + 예시 볼트). 커밋 메시지 제목은 Step에 명시된 것을 쓰고,
  계획서 Global Constraints의 커밋 트레일러 규칙도 함께 따른다.
- 계획서의 코드 블록은 완성본이다 — 임의로 리팩터링하거나 기능을 추가하지 말 것.
  코드 안의 `# ponytail:` 주석은 의도된 단순화 표시이므로 유지한다.

## 핵심 설계 결정 (요약 — 상세는 스펙)

- **md 파일이 진실의 원천**: 실험 1건 = `raw/experiments/*.md` 1개 (YAML frontmatter =
  구조화 레코드). 원문 로그는 본문에 그대로 보존. DB·인덱스 없음.
- **검색은 LLM-select 단일 모드**: 전 레코드 요약 카탈로그(해결 정보 포함) + 위키 아티클
  목록을 LLM에 주고 관련 항목을 고르게 한다. 규모 가정: 연구실당 레코드 ≤50건.
- **LLM 어댑터 격리**: `llm.py`만 호출 방식을 안다. API 키 없이 로컬 CLI subprocess —
  provider `claude`(`claude -p`) / `gemini` / `codex`(`codex exec`), 기본 `claude`.
  structured output은 스키마를 프롬프트에 포함해 JSON 출력 지시 → JSON 추출 → pydantic 검증.
- **§2a 하드 게이트**: log의 필수 필드 재질문은 볼트 `config.yaml`이 결정
  (의미 매칭은 LLM, 게이트 판단은 코드).
- **absorb 자동 체이닝**: log 저장 후 자동 실행(실패는 경고만 — 저장 유지), seed 끝에도
  1회. `needs_review` 레코드는 스킵. `horcrux absorb` 수동 명령은 재시도용.
- **ask는 단일 흐름**: 질문 1회 → 검색 → 응답. 재질문·질의 구조화·증상 분기 없음.
  근거 3단 라벨(레코드 있음 / 위키만 / 둘 다 없음)로 답변 출처를 정직하게 표시.
- 환경변수는 3개뿐: `HORCRUX_VAULT`(기본 `example-vault`), `HORCRUX_PROVIDER`, `HORCRUX_MODEL`.

## 테스트 규칙

- 단위 테스트는 **LLM 호출 없이** 통과해야 한다 — LLM 호출(`generate`/`generate_parsed`)은
  전부 monkeypatch. 실제 CLI 호출은 수동 E2E 스모크 1회뿐.
- 실행: `pip install -e ".[dev]"` (Task 1 이후) → `pytest`

## 환경 주의

- Windows(cp949) 환경 — **모든 파일 I/O에 `encoding="utf-8"` 명시** (계획서 코드에 반영돼 있음).

## 금지 사항 (설계 개정 없이 추가하지 말 것)

스펙의 YAGNI 목록이 근거다. 특히:

- 벡터 검색·임베딩·인덱스 계층 (reindex 명령 포함) — 레코드 수백 건 초과 시 별도 개정으로 도입
- ask의 재질문·질의 구조화·증상 하드 분기
- 웹 UI, 인증/다중 사용자, 자동 스케줄링, 온프레미스 생성 LLM, 모델 재학습, 실데이터 마이그레이션 도구

## 레이어 소유 경계 (병렬 작업 시)

| 영역 | 소유 파일 |
|---|---|
| 프론트 (디스코드 봇) | `src/horcrux/bot.py`, `tests/test_bot.py` |
| 백엔드 (코어) | `src/horcrux/{ingest,diagnose,retrieval,absorb,feedback,records,llm,config,seed}.py` + 기존 테스트 |
| 공용 접점 | `cli.py`, `pyproject.toml`, `README.md`, `docs/**` |

프론트가 의존하는 백엔드 인터페이스(전체 목록):
`parse_log(cfg, text, vcfg)` · `missing_required(parsed, vcfg)` · `to_record(vault, parsed, date)` ·
`save_record(vault, rec, text, summary)` · `save_unparsed(vault, text, err)` · `load_vault_config(vault)` ·
`diagnose(cfg, text)` · `run_absorb(cfg)` · `run_feedback(cfg, id, resolved, cause, note) -> str` ·
`run_seed(cfg, n)`.
시그니처 변경은 백엔드 먼저 수정 후 프론트가 따라간다 — 같은 파일 동시 수정 금지.
