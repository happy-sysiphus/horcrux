# Horcrux MVP — 연구실 실험 기록·문제 진단 시스템 설계

날짜: 2026-07-19
상태: 승인됨 (접근안 A: LLM 위키 완전 이식)
개정 2026-07-20: ask를 LLM 위키 query 수준 단일 흐름으로 단순화(질의 구조화·최소 정보
재질문·증상 하드 분기 제거), 벡터 검색 계층(임베딩 어댑터·인덱서·reindex)을 MVP에서 제외.
개정 2026-07-21: 규모 가정(레코드 ≤50건) 명시, log/seed 후 absorb 자동 체이닝,
absorb의 needs_review 스킵, 카탈로그에 해결 정보 포함(확정 원인 우선), 진단 근거
3단 라벨링, ask 입력 힌트.

## 목적

wet lab(재료/공정/화학) 신입 연구원의 실험 기록과 문제 해결을 보조하는 에이전틱 AI의 MVP.
연구원이 자연어로 실험 로그를 입력하면 LLM이 구조화하여 저장하고, 문제 질의 시 해당 연구실에
축적된 과거 기록에서 유사 사례를 검색해 근거와 함께 답한다. LLM을 활용해 도메인에 제너럴하게
적용 가능한 구조를 지향한다 (도메인 enum 강제 없음, 자유 텍스트 + LLM 분류).

MVP 범위: **코어 파이프라인 + 저장 + 위키 편찬(absorb)**. CLI 대화형 인터페이스. 웹 UI 없음.

## 아키텍처

- **프로그램/데이터 분리**: horcrux 레포 = Python 패키지 + CLI. 연구실 데이터는 별도
  "랩 볼트" 디렉터리(옵시디언으로 열람 가능). 연구실 1곳 = 볼트 1개 = 연구실별 DB.
- **md 파일이 진실의 원천**: 실험 1건 = 마크다운 파일 1개 (YAML frontmatter = 구조화 레코드).
  git이 이력 관리.
- **위키 편찬(absorb) 포함**: LLM이 장비별·재료별·실패모드별 아티클을 편찬 (개인 지식 위키
  패턴 이식). log/seed 후 자동 실행돼 위키가 항상 최신. 진단 시 원본 로그 + 편찬 아티클
  둘 다 컨텍스트로 활용.

## 랩 볼트 레이아웃

```
<lab-vault>/
  config.yaml                       # 연구실별 하드 게이트 설정 (§2a)
  raw/experiments/                  # 실험 1건 = md 1개
    2026-07-19_sputter-dep-001.md
  wiki/
    equipment/<장비명>.md            # 운용 노하우, 자주 나는 문제
    materials/<재료명>.md
    failure-modes/<실패모드>.md      # 과거 사례, 원인 분포, 확인 순서
    _index.md
    _absorb_log.json                # 흡수 완료 추적 (멱등성)
```

## 실험 레코드 스키마 (frontmatter)

```yaml
id: 2026-07-19_sputter-dep-001
date: 2026-07-19
experiment_type: 박막 증착          # 자유 텍스트
objective: ...
equipment: [RF 스퍼터]
materials: [ITO 타겟]
parameters:                         # 통제 가능/불가 라벨링
  - {name: RF power, value: 150W, controllable: true}
results: ...
symptom:                            # §2a 게이트 판정·absorb 실패모드 그룹핑에 사용
  category: low_value | unstable | abnormal | none
  description: ...
suspected_causes:                   # 미확정으로 시작
  - {cause: 타겟 표면 산화, status: unconfirmed}
actions_taken: [...]
resolution:                         # feedback으로 갱신
  resolved: false
  actual_cause: null
  note: ""
needs_review: false                 # 파싱 실패 시 true
```

본문 = `## 원문 로그` (연구원 입력 그대로 보존) + `## 정리` (LLM 서술). 원문 보존 이유:
파싱이 틀려도 데이터를 잃지 않고, absorb가 원문을 다시 읽을 수 있다.

## 파이프라인 (CLI 명령)

| 명령 | 역할 |
|---|---|
| `horcrux log` | 자연어 로그 입력 → LLM 파싱(구조화 JSON) → 필수 필드 부족 시 재질문(최대 3회) → md 저장 → 위키 자동 편찬(absorb 체이닝 — 실패해도 저장은 유지) |
| `horcrux ask` | 문제 질의 → LLM-select 검색(레코드 요약 + 위키 아티클 카탈로그에서 LLM이 관련 항목 선택) → 선택된 원본 전문을 컨텍스트로 응답(사례 인용·원인 후보·확인 방법). 되묻기·증상 분기 없음. 근거 3단 라벨: 레코드 있음 → 라벨 없음, 위키만 → 위키 기반 안내, 둘 다 없음 → 일반 지식 기반 경고 |
| `horcrux absorb` | 신규 레코드를 장비/재료/실패모드 아티클로 편찬. `_absorb_log.json`으로 멱등, `needs_review` 레코드는 스킵. log/seed가 자동 실행하므로 수동 명령은 재시도·전체 재편찬용 |
| `horcrux feedback <id>` | 해결 여부·실제 원인·메모 기록 → resolution/suspected_causes 갱신 |
| `horcrux seed` | 합성 wet lab 로그 생성(개발/데모용) + 마지막에 위키 편찬 1회 |

## §2a 재질문 하드 게이트 — 볼트 설정 파일

하드 게이트 목록은 코드 상수가 아니라 볼트의 `config.yaml`에 둔다 ("연구실 1곳 = 볼트 1개"
이므로 설정도 볼트에 있는 것이 자연스럽다).

```yaml
# <lab-vault>/config.yaml
required_fields:            # 구조 카테고리 하드 게이트 (기본값 = 5개 전부)
  [objective, parameters, results, symptom, actions_taken]
required_parameters:        # 연구실 커스텀 — 이 파라미터는 반드시 기록돼야 함
  - 기판 온도
  - 챔버 습도
```

- `required_fields`: 5개 구조 카테고리(objective/parameters/results/symptom/actions_taken) 중
  어떤 것을 하드 게이트로 켤지 사용자가 선택. 파일이 없으면 기본값 5개 전부.
- `required_parameters`: 연구실 특화 필수 항목 ("우리 랩은 습도 무조건 기록" 같은 규칙).

**의미 매칭은 LLM, 게이트 판단은 코드**: `required_parameters`는 자유 텍스트라 이름 매칭이
문제가 된다 (연구원이 "챔버 습도" 대신 "습도 40%"라고 쓸 수 있음). 파싱 프롬프트에 이 목록을
넘겨 LLM이 항목별 기재/미기재를 판단해 미기재 목록으로 보고하고, 재질문 루프 제어(계속 물을지)는
그 보고를 받아 코드가 결정론적으로 한다. 코드는 LLM이 보고한 이름을 설정 목록과 대조해
목록 밖 항목(환각)은 무시한다.

구조 카테고리의 채움 판정은 결정론적: objective/results는 비어있지 않음, parameters는 1개 이상,
symptom은 category≠none 또는 설명 있음(문제 없으면 LLM이 "문제 없음"으로 명시 기록),
actions_taken은 조치 있음 또는 문제 자체가 없음(category=none).

**v2 연결**: 온보딩(수준 2)이 하는 일은 이 config.yaml을 LLM이 만들어주는 것. MVP에서는
사용자가 직접 편집한다 — 두 수준이 같은 파일로 이어진다.

## LLM

- **생성 LLM**: 어댑터(`llm.py`)로 격리. 기본 클로드(`claude-opus-4-8`, anthropic SDK,
  structured output은 `messages.parse` + pydantic). 추후 제미니 교체 시 이 파일만 수정.
- 설정 환경변수: `HORCRUX_VAULT`, `HORCRUX_PROVIDER`, `HORCRUX_MODEL`.

## 검색 (LLM-select 단일 모드)

규모 가정: **연구실당 레코드 ≤50건** (캡스톤 데모 기준) — 벡터 계층 제외 결정의 근거.

diagnose는 `retrieval.retrieve()`만 호출한다. 전체 레코드의 frontmatter 요약 카탈로그
(id·유형·장비·재료·증상·결과·해결 정보)와 위키 아티클 목록(`<kind>/<slug>`)을 생성 LLM에
주고 관련 항목을 고르게 함(structured output). 해결 정보는 `해결: <확정 원인>` /
`미해결` / `문제 없음` — 유사도가 비슷하면 원인이 확정된 사례를 우선하도록 지시해
feedback 루프가 검색까지 관통한다. 카탈로그에 없는 id(환각)는 코드가 필터.
선택된 원본 레코드 전문 + 위키 아티클이 응답 생성 컨텍스트가 된다.
임베딩·인덱스 불필요, API 키 하나로 동작 — 이 규모에선 맥락을 읽는
LLM 선택이 더 정확하기도 함.

레코드가 수백 건을 넘어 카탈로그가 컨텍스트 한계에 닿으면 그때 벡터 검색 계층을
추가한다(YAGNI 참조). md가 진실의 원천이라 후행 도입에 마이그레이션이 필요 없다.

## 에러 처리

- LLM 파싱 실패(스키마 불일치): 1회 재시도 → 실패 시 원문을 `needs_review: true`로 저장
  (데이터 유실 방지가 최우선).
- 재질문 루프(log)는 최대 3회 후 있는 정보로 진행.
- log의 자동 absorb 실패는 경고만 출력 — 레코드 저장에는 영향 없음 (`horcrux absorb`로 재시도).

## 테스트

- 단위: 레코드 md 라운드트립, LLM-select 검색(카탈로그 생성·환각 id 필터·위키·해결 정보),
  재질문 판정 로직(§2a), 진단 근거 3단 라벨링, absorb 멱등성·needs_review 스킵,
  log→absorb 체이닝 — 전부 LLM 모킹, API 호출 없음.
- 통합: 실제 API로 log→ask 흐름 수동 스모크 1회 (합성 데이터).

## 제외 (YAGNI)

웹 UI, 인증/다중 사용자, 자동 스케줄링, 온프레미스 생성 LLM(어댑터로 대비만),
벡터 검색 계층 전체(임베딩 어댑터·인덱서·`reindex`·`.index/` — 레코드 수백 건 초과로
LLM-select 카탈로그가 컨텍스트 한계에 닿으면 도입),
ask 질의 구조화·최소 정보 재질문·증상 하드 분기(질문 그대로 LLM-select 검색),
학습 루프의 모델 재학습(피드백은 DB 갱신까지만), 실데이터 마이그레이션 도구(실데이터 확보 후).
