# LAB GENE 프론트엔드 — horcrux 웹 UI 설계

날짜: 2026-08-01
상태: 승인됨
참고: `C:\Users\지완\horcrux\UI proto` 목업 7장 (LAB GENE 브랜딩)

## 목적

horcrux MVP(CLI)의 기능 전부를 브라우저 UI로 제공한다. 캡스톤 데모 기준:
`horcrux serve` 명령 하나로 서버를 띄우고 브라우저에서 기록·진단·피드백 전 흐름을 시연한다.
UI 표기 브랜드는 **LAB GENE**, 코드명은 horcrux 유지.

## 범위

**1차 (이 스펙)**: 프로토 ①AI워크스페이스 홈, ②연구 기록 chat, ③과거 기록 분석(ask),
④저장 전 미리보기, ⑤연구노트, ⑦후속 실험 기록 + 실험 피드백 모달.

**2차 (제외)**: ⑥그래프뷰(frontmatter에서 노드·엣지 유도하는 신규 계층 필요),
프로젝트 사이드바(백엔드 개념 없음), 파일 첨부, 음성 입력, 설정 UI, 대화 세션 서버 저장.

## 도메인 구분 — 실험 피드백 vs 후속 실험

- **실험 피드백**: 과거 실험의 사후 갱신 — 해결 여부·확정 원인·코멘트.
  백엔드 `feedback`(update_resolution)에 1:1. LLM 호출 없음, 즉시 반영.
  UI는 ⑤ 레코드 상세의 모달 폼.
- **후속 실험**: 같은 실험을 파라미터만 바꿔 재수행한 **신규 레코드**.
  frontmatter `followup_of`로 기준 레코드에 연결. ⑦ 화면(② 채팅 재사용 + 기준 실험
  패널 + 변경/유지 변수 비교). 저장 시 결과가 기준 실험의 원인을 확인해주면
  "기준 레코드 원인 상태 업데이트" 제안 칩 → 내부적으로 feedback 호출.
- 진입점: ⑤ 레코드 상세에 버튼 2개("실험 피드백", "후속 실험 기록").
  ③에는 진입 버튼을 두지 않는다(기준 레코드가 모호).

## 스택·아키텍처

```
horcrux/
├─ src/horcrux/
│  └─ server.py          # 신규 — FastAPI, 코어 함수 thin wrapper
├─ web/                  # 신규 — Vite + React + TypeScript + Tailwind
│  └─ src/               # pages, components, api client
└─ pyproject.toml        # optional extra [web]: fastapi, uvicorn
```

- `horcrux serve` = uvicorn 기동 + `web/dist` 정적 서빙. 개발은 `vite dev` + 프록시.
- LLM 호출(CLI subprocess, 9~44초)은 동기 엔드포인트(FastAPI 기본 스레드풀) +
  프론트 로딩 인디케이터. 스트리밍 없음 — CLI 어댑터가 최종 텍스트만 반환.
- 볼트·provider는 서버 시작 시 환경변수로 고정. UI 설정 화면 없음.
- 대화 세션·미완료 기록(draft)은 브라우저 localStorage. 서버 저장 없음.

## API (stateless — 대화 누적 원문은 프론트가 관리)

| 엔드포인트 | 역할 | 코어 매핑 |
|---|---|---|
| `POST /api/parse` {text} | 구조화 결과 + 미비 질문 목록 | `parse_log` + `missing_required` |
| `POST /api/records` {text, parsed} | 검토 후 저장, absorb는 BackgroundTasks | `to_record`+`save_record`+absorb |
| `POST /api/records/raw` {text} | 파싱 실패 원문 저장 (needs_review) | `save_unparsed` |
| `POST /api/ask` {text} | 답변 + 선택 사례·위키 메타 + 근거 3단 라벨 | `diagnose` 분해(아래) |
| `GET /api/records` | 목록 (frontmatter 요약) | `list_records`+`load_record` |
| `GET /api/records/{id}` | 전문 (frontmatter + 본문) | `load_record` |
| `POST /api/feedback` | 해결·확정 원인 갱신 | `run_feedback` |
| `GET /api/config` | required_fields·required_parameters·provider | `load_vault_config` |

저장 API는 레코드 md 쓰기까지 동기 완료 후 응답 — "저장됨" 시점에 디스크 확정.
absorb만 백그라운드(실패해도 저장 유지, CLI와 동일 정책). 완료 알림 폴링은 두지 않는다.

## 백엔드 수정 (딱 2개, 나머지 코어 무수정)

1. `records.py`: `ExperimentRecord.followup_of: str | None = None` 필드 추가
   (라운드트립 포함).
2. `diagnose.py`: 답변 문자열만 반환하는 `diagnose()`를 분해 —
   `{answer, records: [카탈로그 메타], wiki: [...], evidence: "records"|"wiki"|"none"}`
   반환 함수 신설, 기존 CLI 출력은 불변.

## 화면 설계

**① 홈**: 큰 입력창 + **기록/질문 모드 토글**(기본: 기록). LLM 의도 분류 없음.
빠른 시작 카드 2개(기록·질문)는 토글 프리셋 역할. 하단 "미완료 기록 N건" =
localStorage draft 목록 → 이어 작성.

**② 연구 기록 chat**: 첫 메시지 전송 → `/parse` 1회 → 우측 패널(구조화 필드·누락 칩·
완성도 게이지 = 채워진 게이트 항목/전체) + 부족 항목 질문을 **하나씩** AI 말풍선 +
퀵답변 칩으로 표시. **답변은 로컬 누적만** — 재파싱 없이 다음 질문 진행, 마지막 gap
답변 후 재파싱 1회로 패널 갱신·잔여 확인. 기록당 LLM 호출 2~3회.
한 답변이 다른 gap을 커버한 경우 다음 질문에 "건너뛰기" 칩. gaps 없으면
"검토 후 저장" 활성 → ④.

**④ 저장 전 미리보기**: parse 결과를 필드 편집 가능한 폼으로(원문 로그는 읽기 전용
보존). 저장하기 → `/records` → ⑤ 상세로 이동. 하단 안내 "저장하면 자동으로
생성됩니다 — 위키 아티클(백그라운드)".

**③ 과거 기록 분석**: 질문 전송 → `/ask` → 유사 사례 카드(id·실험유형·
해결/미해결/문제없음 라벨 — 유사도 % 없음) + 원인 후보·확인 방법(답변 텍스트 섹션
렌더) + 근거 3단 라벨 배너. 카드 클릭 → ⑤ 상세.

**⑤ 연구노트**: 좌 목록(검색·필터: 장비/증상/기간 — 클라이언트 필터) + 우 상세.
읽기 전용. `followup_of` 있으면 "이어진 실험" 링크 표시. 버튼 2개:
실험 피드백(모달: 해결 여부·확정 원인·코멘트 → `/feedback`), 후속 실험 기록(→⑦).

**⑦ 후속 실험 기록**: 좌 기준 실험 카드(frontmatter 요약) + 중앙 ② 채팅 재사용 +
우측 비교 패널(기준 vs 신규 파싱 결과의 장비·재료·parameters 클라이언트 diff →
변경/유지 변수). 저장 = `followup_of` 포함 신규 레코드. 칩 노출 조건은 결정론:
**기준 레코드가 미해결이면** 저장 시 "기준 실험 원인 상태 업데이트" 옵션을 항상
표시(확정 원인은 기준의 suspected_causes에서 선택 또는 직접 입력, LLM 판단 없음)
→ 선택 시 저장 + `/feedback` 순차 호출.

**사이드바 공통**: 대화 히스토리(localStorage) — 제목은 첫 메시지 30자, 파싱 후
experiment_type·objective로 자동 갱신(제목용 LLM 호출 없음). 프로젝트 섹션 생략.

## 에러 처리

- LLM 실패·타임아웃: 에러 토스트 + 재시도 버튼 (백엔드가 1회 재생성은 이미 수행).
- ② 파싱 반복 실패: "원문만 저장(needs_review)" 제안 → `/records/raw`. CLI와 동일 정책.
- 존재하지 않는 레코드 id (feedback 등): 404 + 토스트.

## 테스트

- server.py: 코어 함수 모킹한 FastAPI TestClient 단위 테스트 (엔드포인트별 계약).
- 프론트: API 클라이언트 모킹한 핵심 컴포넌트 테스트 최소 — ② 게이지·칩 흐름,
  ⑦ 변수 diff. 러너 vitest.
- E2E 수동 스모크 1회: 실제 CLI provider로 기록→ask→피드백→후속 흐름.

## 제외 (YAGNI)

그래프뷰·프로젝트·파일 첨부·음성 입력·설정 UI·대화 서버 저장·유사도 % 표시·
absorb 완료 알림 폴링·LLM 의도 분류·인증(로컬 단일 사용자).
