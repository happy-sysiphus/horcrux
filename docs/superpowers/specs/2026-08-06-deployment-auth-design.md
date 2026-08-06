# 배포·멀티테넌시·인증 설계

날짜: 2026-08-06
상태: 승인됨
전제: 실제 연구실 파일럿 (연구실 1~2곳, "특정 컴퓨터가 꺼져 있어도 시스템이 돌아간다")

## 결정 요약

| 갈림길 | 결정 |
|---|---|
| 데이터 계층 | md 볼트 유지 + 클라우드 영구 볼륨 + 외부 백업. Postgres 전면 전환 안 함 |
| 호스팅 | Railway (도커, GitHub 푸시 자동 배포, 영구 볼륨) |
| 인증·DB | Supabase 한 방 — Auth(구글+이메일) + Postgres(매핑) + Storage(백업) |
| 멀티테넌시 | 1인 1연구실, 초대 코드 합류, 역할 2단(관리자/멤버). 스키마는 다대다 |
| LLM | 기본 중앙 API 키(온보딩 벽 제로) + 연구실별 자기 크레덴셜은 고급 옵션 |
| 디스코드 봇 | 삭제 (웹 프론트가 대체) |

## 아키텍처

```
Railway (도커 컨테이너)
├─ FastAPI + React 정적 서빙 (기존 horcrux serve)
├─ 영구 볼륨 DATA_DIR=/data
│  └─ vaults/<lab_id>/          # 연구실별 볼트 — 내부 md 구조 무변경
└─ 백업: 일 1회 볼트 zip → Supabase Storage (서버 내 타이머 스레드)

Supabase
├─ Auth: 구글 로그인 + 이메일/비번, 비번 재설정 내장
├─ Postgres: labs, lab_members, llm_usage
└─ Storage: vault-backups 버킷
```

- "연구실 1곳 = 볼트 1개" 원칙을 디렉토리로 확장: `DATA_DIR/vaults/<lab_id>/`.
- 코어 함수 시그니처 무변경 — `Config.vault`가 요청 컨텍스트에서 결정될 뿐.
- 볼트 쓰기 락: 기존 전역 락 → 연구실별 락 (lab_id 키 딕셔너리).

## 인증 흐름

1. 프론트가 Supabase SDK로 로그인(구글 또는 이메일/비번) → access token(JWT).
2. 모든 API 요청에 `Authorization: Bearer <token>`.
3. FastAPI 미들웨어: Supabase JWT 검증(`SUPABASE_JWT_SECRET`) → user_id →
   lab_members 조회 → lab_id → `cfg.vault = DATA_DIR/vaults/<lab_id>` 주입.
4. 소속 연구실 없는 사용자는 온보딩 API만 접근 가능(연구실 생성 / 초대 코드 입력).
- 서버는 Supabase **service key**로 DB 접근 (RLS는 서버 경유 구조라 1차 생략).

## DB 스키마 (Supabase Postgres)

```sql
labs (
  id uuid pk default gen_random_uuid(),
  name text not null,
  invite_code text unique not null,       -- 재발급 가능
  created_by uuid not null,               -- auth.users.id
  llm_mode text not null default 'central',  -- 'central' | 'own'
  llm_provider text,                      -- own일 때: claude|api (1차 한정)
  llm_credential text,                    -- own일 때: 암호화 토큰/키 (Fernet, 서버 env 키)
  daily_llm_limit int not null default 200,
  created_at timestamptz default now()
)
lab_members (
  lab_id uuid fk, user_id uuid, role text not null default 'member',  -- 'admin'|'member'
  pk (lab_id, user_id)
)
llm_usage (
  lab_id uuid, day date, count int not null default 0,
  pk (lab_id, day)
)
```

UI는 1인 1연구실이지만 lab_members가 다대다라 다중 소속은 나중에 UI만 추가.

## LLM 계층

- **중앙 모드(기본)**: `api` provider 신설 — anthropic SDK 복귀(어댑터에 분기 추가,
  CLI 3종 분기는 유지). 키는 서버 env `ANTHROPIC_API_KEY`, 모델은 `HORCRUX_MODEL`.
  가입 즉시 동작.
- **연구실 크레덴셜 모드(고급, 관리자 설정)**: claude `setup-token` 장기 토큰 또는
  API 키를 등록 → Fernet 암호화해 labs.llm_credential 저장 → 호출 시 subprocess env
  주입(claude: `CLAUDE_CODE_OAUTH_TOKEN`, api: 키 교체). 등록은 운영자 대행 가능.
  크레덴셜 실패(만료 등) 시 그 연구실에 "재등록 필요" 에러 반환.
- **사용량 상한**: LLM 유발 API 요청(parse/ask/records) 1건마다 llm_usage upsert 증가.
  `daily_llm_limit` 초과 시 429 + 안내 메시지(관리자에게 상한 상향/자기 크레덴셜 전환 안내).
  중앙 키 보호 장치.

## 서버 환경변수

`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`,
`ANTHROPIC_API_KEY`(중앙 모드), `HORCRUX_MODEL`, `CRED_ENCRYPTION_KEY`(Fernet),
`DATA_DIR`(기본 /data).

## 신규·변경 API

| 엔드포인트 | 역할 |
|---|---|
| `POST /api/labs` | 연구실 생성 (생성자 = admin, 초대 코드 발급) |
| `POST /api/labs/join` {invite_code} | 초대 코드로 합류 |
| `GET /api/labs/me` | 내 연구실·역할·사용량·llm_mode |
| `PUT /api/labs/settings` | (admin) 이름·상한·LLM 모드/크레덴셜·초대 코드 재발급 |
| 기존 전부 | JWT 필수 + lab 컨텍스트로 동작 (무소속이면 403) |

## 제거

- `bot.py`, discord 의존성, 관련 테스트·문서 언급 삭제.
- CLI(`horcrux log` 등)는 로컬 개발용으로 유지 — 서버 배포와 무관.

## 에러 처리

- JWT 없음/무효: 401. 무소속: 403 + 온보딩 안내. 상한 초과: 429.
- 연구실 크레덴셜 실패: 502 + "관리자에게 크레덴셜 재등록 요청" 메시지.
- 백업 실패: 로그만 (다음 주기 재시도) — 서비스 영향 없음.

## 테스트

- 미들웨어: JWT 위조/만료/무소속 케이스 (Supabase 모킹).
- lab 컨텍스트: 연구실 A 사용자가 B 볼트에 접근 불가.
- 사용량 상한: 경계값(한도 도달 → 429).
- 크레덴셜: 암호화 라운드트립, env 주입 커맨드 구성 (subprocess 모킹).
- 배포 스모크: Railway 스테이징에서 가입→연구실 생성→기록→질의 수동 1회.

## 보류 (YAGNI)

Postgres 전면 전환, RLS, 다중 소속 UI, 봇 재도입, 이메일 초대(코드 방식으로 충분),
연구실 삭제·탈퇴 흐름(파일럿에선 운영자 수동), 조직 단위 과금,
연구실 크레덴셜의 gemini/codex 지원(파일 기반 크레덴셜 주입이 복잡 — claude 토큰·API 키로 시작).
