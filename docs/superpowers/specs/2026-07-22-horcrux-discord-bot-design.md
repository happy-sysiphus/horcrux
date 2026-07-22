# Horcrux 디스코드 봇 프론트엔드 — 설계

날짜: 2026-07-22
상태: 승인됨 (접근안 A: 단일 프로세스 봇)

## 목적

Horcrux 백엔드(실험 기록·진단 파이프라인)의 프론트엔드. 봇 프로세스를 랩서버에 상주시키고,
연구원은 디스코드 채널에 자연어로 실험 로그를 쓰거나 문제를 질문한다. 웹 UI·데스크톱 앱 없음 —
메신저가 프론트다. 열람(레코드·위키 브라우징)은 기존대로 옵시디언.

카카오톡은 v2로 미룸: 개인용 봇 API가 없어 카카오톡 채널 + 카카오 i 오픈빌더 스킬서버
(공개 HTTPS 엔드포인트) 구성이 필요해 MVP 부담이 큼. 디스코드는 봇 토큰만으로 동작하고
서버에서 아웃바운드 연결이라 공인 IP·HTTPS가 불필요.

## 아키텍처 (접근안 A: 단일 프로세스)

- 신규 모듈 **`src/horcrux/bot.py` 하나**. discord.py 봇이 horcrux 코어 함수를 직접 임포트.
  HTTP API 계층 없음 — 카톡·웹 추가가 실제로 필요해질 때 그때 분리(YAGNI).
- `cli.py`에 `horcrux bot` 서브커맨드 추가. `pyproject.toml`에 `discord.py`(v2.6.x) 의존성 추가.
- 재질문 루프가 함수 호출 사이 상태 유지를 요구하므로 같은 프로세스가 가장 단순.
- 기존 CLI 명령(`log`/`ask`/…)은 그대로 유지 — 봇은 병행 프론트.

## 설정

| 항목 | 값 |
|---|---|
| `HORCRUX_DISCORD_TOKEN` | 봇 토큰. 환경변수로만 — 코드·레포에 절대 넣지 않음 |
| `HORCRUX_LOG_CHANNEL` | log 채널 이름. 기본 `실험로그` |
| `HORCRUX_ASK_CHANNEL` | ask 채널 이름. 기본 `질문` |

기존 `HORCRUX_VAULT`/`HORCRUX_PROVIDER`/`HORCRUX_MODEL` 그대로 사용.
랩서버에도 선택한 CLI(claude/gemini/codex)가 설치·로그인돼 있어야 한다 (백엔드 요구사항 동일).

## 봇 UX (하이브리드)

**채널 매핑** — 명령어 없이 채널에 쓰면 동작:

- `#실험로그` 채널 메시지 → log 파이프라인:
  1. `parse_log` → `missing_required`로 §2a 게이트 판정 (기존 로직 그대로)
  2. 부족 필드 있으면 봇이 재질문 → **같은 채널·같은 유저**의 다음 메시지를 대기
     (`wait_for('message', check, timeout=600)`). 타임아웃·빈 응답이면 있는 정보로 저장 진행
  3. 최대 3회 후 저장 → **저장 확인(경로+요약)을 즉시 회신**. 위키 편찬(absorb)은 후속
     단계로 분리 — 완료 시 "위키 갱신: n건" 별도 메시지(0건이면 생략), 실패해도 저장은
     유지되고 경고만 회신(기존 정책)
  4. 필수 정보 빈 채 저장 시 그 사실 함께 회신. 봇 회신은 전부 원 메시지에 **답장(reply)**
     형식 — 다중 유저 채널에서 귀속 명확 + 작성자에게 알림
  - 파싱 실패: 기존과 동일하게 원문을 `needs_review: true`로 저장 후 안내 (데이터 유실 방지)
- `#질문` 채널 메시지 → `diagnose(cfg, text)` → 답변 회신 (2000자 초과 시 분할 전송)

**슬래시 커맨드** — 인자형·단발 명령:

- `/feedback record_id resolved cause note` → `run_feedback`
- `/absorb` → `run_absorb`, 갱신 건수 회신
- `/seed n` → `run_seed`, 저장 건수 회신
- 개발 중엔 guild-scoped `tree.sync(guild=...)` (글로벌 sync는 전파 지연 최대 1시간)

**첨부 파일**: 메시지 첨부(실험 사진 등)는 다운로드해 `<볼트>/raw/attachments/<레코드id>/`에
저장하고 md 원문에 옵시디언 임베드 링크(`![[...]]`)를 추가 — needs_review 저장 경로도 동일
보존(단, 이 경로는 본문 링크 없이 레코드 id 폴더 규약으로만 연결).
LLM이 이미지 내용을 분석하지는 않음(보관+링크만 — CLI 텍스트 파이프라인, 비전 없음).
ask 채널 첨부는 "분석에 사용되지 않음" 안내만. 첨부만 있고 텍스트 없는 log 메시지는
기록 불가 안내.

**진행상황 표시**: LLM 구간마다 접수 즉시 상태 메시지 회신("🔬 로그 분석 중...",
"🔍 검색·진단 중...", 재질문 답변 후 "반영 중...") + typing 표시. 슬래시 커맨드는
`defer()`의 "생각 중..." 표시. CLI subprocess 특성상 완료까지 진행률 신호가 없어
단계별 %·스트리밍은 제공하지 않음 (YAGNI).

## 동시성·안전

- LLM 호출은 블로킹 subprocess(최대 300초) — `asyncio.to_thread`로 감싸 이벤트 루프 보호.
- 재질문 세션은 (채널 id, 유저 id) 키 dict — 유저·채널당 진행 중 세션 1개.
  재질문 답변 대기 중 메시지는 답변으로 소비. LLM 처리 중(대기 리스너 없음)에 온
  메시지는 무통보 유실 대신 "처리 중" 안내를 회신.
- 봇 자신의 메시지는 무시 (`message.author == bot.user` — on_message 재귀 방지).
- **볼트 쓰기(레코드 저장·첨부·absorb)는 프로세스 내 전역 락으로 직렬화** — 동시 저장 시
  record id 순번 경쟁(레코드 덮어쓰기 유실)·`_absorb_log.json` 경쟁 방지. LLM 호출 구간은
  락 밖이라 병렬 유지.
- `message_content`는 privileged intent — Discord 개발자 포털에서 켜고 코드에서도
  `intents.message_content = True` 명시 필요.

## 프론트↔백엔드 인터페이스 계약

봇이 의존하는 코어 함수 전부 (이 시그니처가 레이어 경계 — `AGENTS.md`에 문서화):

```python
ingest.parse_log(cfg, text, vcfg) -> ParsedLog
ingest.missing_required(parsed, vcfg) -> list[str]      # 재질문 문항 목록
ingest.to_record(vault, parsed, date) -> ExperimentRecord
ingest.save_unparsed(vault, text, err) -> Path          # 파싱 실패 원문 needs_review 저장 (신설)
config.load_vault_config(vault) -> VaultConfig
records.save_record(vault, rec, text, summary) -> Path
diagnose.diagnose(cfg, text) -> str
absorb.run_absorb(cfg) -> int
feedback.run_feedback(cfg, record_id, resolved, cause, note) -> str   # 변경
seed.run_seed(cfg, n) -> int
```

**백엔드 변경은 2건뿐**: (1) `run_feedback`이 print 대신 결과 메시지 문자열을 반환하고
CLI 경로는 `print(run_feedback(...))`로 유지, (2) `run_log`의 파싱 실패 폴백(needs_review
저장)을 `save_unparsed`로 추출해 CLI·봇이 공유 (동일 로직 복제 방지). 그 외 백엔드
파일은 손대지 않는다.

## 테스트

- 봇 대화 로직을 discord 객체 비의존 순수 로직으로 분리 — "텍스트 입력 → 응답 텍스트 목록 +
  다음 상태" 형태로 단위 테스트 (`tests/test_bot.py`). LLM은 기존 패턴대로 모킹,
  discord.py 모킹은 최소화.
- 커버 대상: 채널 매핑 분기, 재질문 루프(0·1·3회, 타임아웃/빈 응답 스킵), 파싱 실패
  needs_review 경로, absorb 체이닝 실패 경고, 2000자 분할, 슬래시 커맨드 3종.
- 실행: `python -m pytest -q --basetemp=.pytest_tmp` (샌드박스 temp 권한 문제).
- 통합: 실제 토큰 + 테스트 길드에서 수동 스모크 1회 — log→재질문→저장→위키 갱신, ask,
  /feedback 각 1회.

## 개발 방식 (Agent Teams 미사용 결정)

단일 세션 TDD 순차 구현. Agent Teams(실험 기능) 검토 결과: 이 규모(신규 1파일 중심)에선
팀 조율·컨텍스트 배수 오버헤드가 병렬 이득을 초과. 대신 **레이어 소유 경계를 `AGENTS.md`에
문서화**해 이후 어떤 병렬화(팀·멀티세션)에도 재사용:

| 영역 | 소유 파일 |
|---|---|
| 프론트 | `src/horcrux/bot.py`, `tests/test_bot.py` |
| 백엔드 | `src/horcrux/{ingest,diagnose,retrieval,absorb,feedback,records,llm,config,seed}.py` + 기존 테스트 |
| 공용 접점 | `cli.py`, `pyproject.toml`, `README.md`, `docs/**` |

경계 규칙: 프론트는 위 인터페이스 계약의 함수만 사용. 시그니처 변경이 필요하면 백엔드 먼저
수정 후 프론트가 따라간다 (동시 수정 금지).

## 개발 도구

- **pyright-lsp** (선택): `/plugin install pyright-lsp@claude-plugins-official` +
  `npm install -g pyright`. 없어도 pytest로 충분.
- **context7** (설치됨): discord.py 등 API 문서 조회.
- 웹용 도구(typescript-lsp, Playwright, Chrome DevTools MCP, frontend-design)는 웹 UI가
  없으므로 설치하지 않음.

## 구현 단계

0. **준비 (사용자 수동)**: Discord 개발자 포털 — 앱 생성 → Bot 추가 → Message Content
   Intent 활성화 → 토큰 발급 → 테스트 서버 초대 (메시지 읽기/쓰기 권한)
1. **TDD 구현**: `tests/test_bot.py` 실패 테스트 → `bot.py` 구현 → `cli.py`·`pyproject.toml`
   → `run_feedback` 반환값 변경
2. **문서**: `AGENTS.md` 경계 문서화, `README.md` 봇 설정·실행 절차
3. **검증**: 전체 pytest 통과 + 테스트 길드 수동 스모크
4. **머지**: worktree 브랜치에서 작업 후 main 병합 (기존 플로우)

## 알려진 한계 (수용)

- 재질문 세션은 인메모리 — 봇 재시작·크래시 시 진행 중 세션 유실. 원문·답변이 디스코드
  채널 히스토리에 그대로 남으므로 재입력(복붙)으로 복구. `wait_for` 기반 대화 루프 특성상
  영속화는 이벤트 구동형 전면 재설계가 필요해 MVP 가치 대비 비용 과대.

## 제외 (YAGNI)

카카오톡 어댑터(오픈빌더·HTTPS 준비 포함), 웹 대시보드, FastAPI 등 HTTP API 계층,
DM 자연어 의도 분류, 다중 길드·다중 볼트 매핑(길드 1개 = 볼트 1개 고정), 봇용 권한·인증
(채널 접근권이 곧 사용권), 재질문 세션 영속화(봇 재시작 복원), 첨부 이미지 내용 분석(비전),
Agent Teams 상시 팀 구성.
