# Horcrux MVP — 연구실 실험 기록·문제 진단 시스템 설계

날짜: 2026-07-19
상태: 승인됨 (접근안 A: LLM 위키 완전 이식)

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
  git이 이력 관리. 검색 인덱스는 md에서 언제든 재생성 가능한 파생 캐시.
- **위키 편찬(absorb) 포함**: LLM이 장비별·재료별·실패모드별 아티클을 편찬 (개인 지식 위키
  패턴 이식). 진단 시 원본 로그 + 편찬 아티클 둘 다 컨텍스트로 활용.

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
  .index/                           # 파생 검색 캐시 (embeddings.npy + meta.json)
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
symptom:                            # 진단 분기의 키
  category: low_value | unstable | abnormal | none
  description: ...
suspected_causes:                   # 미확정으로 시작
  - {cause: 타겟 표면 산화, status: unconfirmed}
actions_taken: [...]
resolution:                         # feedback으로 갱신
  resolved: false
  actual_cause: null
needs_review: false                 # 파싱 실패 시 true
```

본문 = `## 원문 로그` (연구원 입력 그대로 보존) + `## 정리` (LLM 서술). 원문 보존 이유:
파싱이 틀려도 데이터를 잃지 않고, absorb가 원문을 다시 읽을 수 있다.

## 파이프라인 (CLI 명령)

| 명령 | 역할 |
|---|---|
| `horcrux log` | 자연어 로그 입력 → LLM 파싱(구조화 JSON) → 필수 필드 부족 시 재질문(최대 3회) → md 저장 → 인덱스 갱신 |
| `horcrux ask` | 문제 질의 → 질의 구조화 + 최소 정보 되묻기 → 증상 분기: ①값낮음/②불안정 → 유사사례 검색 + 응답(사례 인용·원인 후보·확인 방법), ③비정상 → 설계 결함 의심으로 사람 연결 안내 |
| `horcrux absorb` | 신규 레코드를 장비/재료/실패모드 아티클로 편찬. `_absorb_log.json`으로 멱등 |
| `horcrux feedback <id>` | 해결 여부·실제 원인 기록 → resolution/suspected_causes 갱신 → 재인덱싱 |
| `horcrux reindex` | 벡터 인덱스 전체 재생성 (vector 모드 전환 시 1회 실행) |
| `horcrux seed` | 합성 wet lab 로그 생성(개발/데모용) |

최소 정보 (ask): 증상 설명 + (장비 또는 실험 유형).

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

## LLM / 임베딩

- **생성 LLM**: 어댑터(`llm.py`)로 격리. 기본 클로드(`claude-opus-4-8`, anthropic SDK,
  structured output은 `messages.parse` + pydantic). 추후 제미니 교체 시 이 파일만 수정.
- **임베딩**: 생성 LLM과 동일하게 어댑터(`embeddings.py`)로 격리. `HORCRUX_EMBED_PROVIDER`로
  분기 — `local`(sentence-transformers, 기본 `google/embeddinggemma-300m`, 실데이터 단계용) 구현,
  `gemini`/`voyage`는 NotImplementedError 자리만. MVP 기본 검색은 임베딩을 아예 쓰지 않음(아래 참조).
  sentence-transformers는 optional extra(`pip install -e ".[vector]"`)로 분리.
- 설정 환경변수: `HORCRUX_VAULT`, `HORCRUX_PROVIDER`, `HORCRUX_MODEL`,
  `HORCRUX_EMBED_PROVIDER`, `HORCRUX_EMBED_MODEL`, `HORCRUX_SEARCH`, `HORCRUX_SEARCH_THRESHOLD`.

## 검색 (이중 모드, 자동 전환)

diagnose는 `retrieval.retrieve()`만 호출한다. 모드는 `HORCRUX_SEARCH`(auto|llm|vector, 기본 auto):
auto는 레코드 수 ≤ `HORCRUX_SEARCH_THRESHOLD`(기본 200)이면 llm, 초과면 vector.

- **llm_select (MVP 기본)**: 전체 레코드의 frontmatter 요약 카탈로그(id·유형·장비·재료·증상·결과)를
  생성 LLM에 주고 유사 사례 top-k id를 고르게 함(structured output). 임베딩·인덱스 불필요,
  API 키 하나로 동작. 수십~수백 건 규모에선 맥락을 읽는 LLM 선택이 더 정확하기도 함.
- **vector (수백 건 초과 시 자동 전환)**: frontmatter 필터(장비·재료·증상 겹침) → 부분집합 내
  코사인 유사도 랭킹 → 비면 전체 랭킹. `.index/`는 vector 모드에서만 생성·갱신.
  인덱스에 임베딩 모델명을 기록해 불일치 시 에러로 reindex를 안내.

두 모드 모두 top-k 원본 레코드 + 관련 위키 아티클을 응답 생성 컨텍스트로 사용.

## 에러 처리

- LLM 파싱 실패(스키마 불일치): 1회 재시도 → 실패 시 원문을 `needs_review: true`로 저장
  (데이터 유실 방지가 최우선).
- 인덱스는 파생물이므로 손상 시 `reindex`로 복구.
- 재질문 루프는 최대 3회 후 있는 정보로 진행.

## 테스트

- 단위: 레코드 md 라운드트립, 인덱서(가짜 임베더), 검색 디스패처(모드 자동 전환·LLM-select),
  재질문 판정 로직, 증상 분기, absorb 멱등성 — 전부 LLM 모킹, API 호출 없음.
- 통합: 실제 API로 log→ask 흐름 수동 스모크 1회 (합성 데이터).

## 제외 (YAGNI)

웹 UI, 인증/다중 사용자, 자동 스케줄링, 온프레미스 생성 LLM(어댑터로 대비만),
클라우드 임베딩 제공자 구현(gemini/voyage — 어댑터 자리만, 전환 시점에 구현),
학습 루프의 모델 재학습(피드백은 DB 갱신까지만), 실데이터 마이그레이션 도구(실데이터 확보 후).
