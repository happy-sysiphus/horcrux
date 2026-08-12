# UI 수정 배치 + 제미나이 + Q&A 이력 (2026-08-12)

사용자 요청 8건 묶음. 검증 절차 생략(사용자 지시) — 구현 → 빌드 → frontend 브랜치 커밋·푸시만.

## ① 중복 저장 버그 수정

증상: 동일 내용 레코드가 같은 초에 3개 생성됨(볼트에서 확인, 바이트 동일).

- **서버 멱등(핵심)**: `api_save`에서 연구실별로 마지막 저장의 (rawText+parsed 해시, id, 시각)을
  메모리에 캐시. 60초 내 동일 해시 재요청이면 생성 없이 기존 id 반환. 재시작 시 캐시 리셋 허용.
- **IME 가드**: ChatPane 입력의 Enter 핸들러에 `!e.nativeEvent.isComposing` 추가
  (한글 조합 중 Enter 이중 발화 — 확정 버그).
- **ref 가드**: Preview `onSave`의 진행중·savedId 가드를 state가 아닌 ref로 (동기 차단).
- 기존 중복 파일 삭제: `박막-증착-003/004`, `mxene-박막-패터닝-및-에칭-002/003` (내용 동일 확인됨).

## ② AI 짧은 제목

- `ParsedLog`·`ExperimentRecord`에 `title: str = ""` 추가. 파싱 프롬프트에
  "6~15자 짧은 제목" 지시 추가. `_META_KEYS`에 "title".
- 표시 우선순위 `title || objective || experiment_type` — 연구노트 목록·상세 헤더·
  그래프 라벨·세션 제목(useLogLoop)·RecordCard 전부.
- Preview 기본 정보 카드에 제목 편집 필드 추가.
- 기존 기록은 title 없음 → 기존 표시 그대로 (fallback).

## ③ 연구노트 편집

- 백엔드: `PUT /api/records/{record_id}` 신설 — 참고문헌 PUT과 동일 패턴
  (lab_cfg → _existing_record → lab_lock → load_record → 필드 반영 → write_md).
  입력: 편집 가능 메타(title, experiment_type, objective, equipment, materials,
  parameters, results, symptom, suspected_causes, actions_taken, notes) 부분 갱신 + `body?: str`.
  id·date·resolution·needs_review·references·followup_of는 제외(불변 또는 전용 경로).
- 프론트: Notes 상세에 "수정" 버튼 → 편집 모드 토글. Preview의 Field/DraftField
  export해 재사용. 본문은 textarea. 저장 → PUT → 상세·목록 갱신. api.ts에 `updateRecord`.

## ④ 되감기·포크 아이콘화

- ChatPane: 텍스트 라벨 제거, `↩` `⑂` 아이콘 버튼만 상시 노출
  (`md:opacity-0 md:group-hover:opacity-100` 게이트 삭제). `title` 툴팁으로 설명.

## ⑤ 세션 ⋯ 메뉴 (고정·이름변경·삭제)

- `Session.pinned?: boolean`. `listSessions` 정렬: pinned 우선 → createdAt desc.
- Sidebar 세션 행: 호버 시 ⋯ 버튼(모바일 상시) → 드롭다운(고정/고정 해제, 이름 변경, 삭제).
  이름 변경은 행 인라인 input 전환(Enter 확정, Esc 취소). 삭제는 confirm 1회.
  고정 세션은 📌 접두. 드롭다운은 바깥 클릭으로 닫힘. 전부 localStorage(store.ts).

## ⑥ 연구실 카드 이동

- 데스크톱: 흰 aside 하단 카드 제거 → 검은 레일(w-52) 최하단에 연구실 이름+역할+로그아웃
  (mt-auto, 어두운 톤 텍스트). 모바일 드로어: 현 위치 유지.

## ⑦ Q&A 이력 저장 + 관례 학습 (그릴링 확정: 소비까지 포함)

**수집** — 저장 시 세션 messages에서 (AI 질문 → 직후 사용자 답) 쌍 추출
("건너뛰기" 답 제외, 질문은 chips 있는 AI 메시지로 식별).
`RecordIn.qa: list[{question, answer}] = []` → `save_record`가 본문 끝에
`## 재질문` 섹션으로 기록 (frontmatter 아님 — 위키 편찬 LLM이 자연히 읽도록).

**편찬** (그릴링 Q3) — `run_absorb`가 새 레코드 처리 후, 새 레코드 중 `## 재질문`
섹션이 있는 것들 + 기존 관례 문서를 LLM에 넘겨 `wiki/_관례.md`를 다시 쓴다.
내용: 반복되는 질문·답 패턴을 간결한 관례 규칙으로 (예: "온도 단위 미표기 시 ℃",
"장비 'ALD'는 ALD-02"). 위키에 두므로 옵시디언에서 직접 수정 가능, 진단 근거에도 포함.

**주입** (그릴링 Q2=a) — `parse_log`가 `wiki/_관례.md`가 있으면 본문을
`[연구실 관례]` 섹션으로 사용자 메시지에 첨부 (필수 파라미터 목록과 동일 패턴).
LLM이 관례를 반영해 필드를 채우므로 재질문이 자연 감소. 추정값은 미리보기에서 수정 가능.

## ⑧ 제미나이 provider

- `lab_cfg`: 코덱스·제미나이를 `{"codex": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}`
  표로 통합 — 키 있으면 주입, 없으면 서버 머신 CLI 로그인 사용. claude(토큰 필수)·api는 불변.
- Settings 셀렉트에 "Gemini CLI — API 키 또는 서버 로그인" 추가, 키-선택 규칙 codex와 공유.
- Dockerfile에 `@google/gemini-cli` 추가.

## 제외 (YAGNI)

needs_review 자동 해제, 제목 일괄 재생성(기존 기록).
