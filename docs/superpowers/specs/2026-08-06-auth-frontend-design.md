# 인증·온보딩 설계 (풀스택)

2026-08-06 · 브레인스토밍 + 그릴링 확정본. 백엔드 병합본(main 08dfdfd) 기준으로 계약 검증함.

## 그릴링 확정 (2026-08-06)

- **풀스택 전환**: 백엔드 3건(auth-config·labs/me 확장·참고문헌 PUT)도 이 세션이
  frontend 브랜치에서 직접 구현한다 (백엔드 main 머지로 충돌 위험 해소, 사용자 승인).
- **분담**: 코드 전부 + 로컬 배포 모드 검증까지 이 세션. Supabase 프로젝트·구글
  OAuth·schema.sql 실행·Railway 배포는 사용자가 체크리스트 문서 따라 병행.
- **설정 저장 UX**: 저장 버튼 하나(변경 필드만 PUT, 모드 own인데 크레덴셜 없으면
  저장 비활성). 초대 코드 재발급만 즉시 실행 버튼.
- **끝선**: 로컬 배포 모드 E2E(사용자 Supabase 값 도착 후)까지. Railway는 체크리스트.

## 목적

배포 모드(Railway+Supabase)에서 구글 로그인 → 연구실 온보딩 → 연구실 컨텍스트로
앱 사용. 로컬 모드(`deploy is None`)에서는 지금처럼 인증 없이 동작한다.

## 확정 결정

- 로그인은 **구글만** (이메일/비번 UI 없음 — Supabase 백엔드 계약과 무충돌)
- Supabase 접속 정보는 **무인증 `GET /api/auth-config`** 로 받는다 (신설 요청, 아래)
- 429 전역 배너는 만들지 않는다 — 서버가 한국어 detail을 주므로 기존 화면별
  에러 표시가 그대로 받는다
- 새 의존성: `@supabase/supabase-js` 1개

## 백엔드 계약 — 병합본에서 확인된 것 (그대로 사용)

| 엔드포인트 | 확인된 형태 |
|---|---|
| `POST /api/labs` {name} | `{"lab": {...}, "role": "admin"}` · 소속 있으면 409 · 로컬 404 |
| `POST /api/labs/join` {invite_code} | `{"lab": {...}, "role": "member"}` · 코드 오류 404 · 소속 있으면 409 |
| `GET /api/labs/me` | `{"lab": {...} \| null, "role": "admin"\|"member"\|null}` (로컬은 null/null) |
| `PUT /api/labs/settings` | body: name? daily_llm_limit? llm_mode? llm_provider?+llm_credential? rotate_invite? → `{"ok": true}` · 비관리자 403 |
| 기존 전부 | 배포 모드에서 Bearer 필수. 401(미로그인)·403(무소속)·429(상한, detail 한국어) |

lab 객체: `id, name, llm_mode, llm_provider, daily_llm_limit` (+ admin일 때만 `invite_code`).
`llm_credential`은 절대 응답에 없음(화이트리스트) — 설정 폼은 write-only.

## 백엔드 계약 — 추가 요청 3건 (요청서로 전달)

1. **`GET /api/auth-config` 신설 (무인증, 최우선)**
   `{"deploy": bool, "supabase_url": str|null, "supabase_anon_key": str|null}`.
   현 병합본은 `/api/config`가 require_lab 뒤라 로그인 전에 아무것도 못 받는다 —
   이 엔드포인트 없이는 프론트가 Supabase 초기화 불가. anon key는 공개 전제 값.
2. **`GET /api/labs/me` 확장** — `usage_today: int`(오늘 llm_usage), admin일 때
   `members: [{email, role}]`. 설정 화면의 "일일 사용량/상한 표시"·"멤버 목록"
   요구사항에 대응하는 필드가 현 응답에 없다.
3. **(기존 미반영) 참고문헌 PUT** — `2026-08-06-references-backend-request.md` 그대로.

2번 반영 전까지 설정 화면은 해당 항목을 "—"로 표시한다(크래시 금지 원칙).

## 아키텍처 — AuthProvider (web/src/auth.tsx 신설)

부팅 순서: `GET /api/auth-config` → 분기.

```
deploy=false → 무인증 모드: 지금 동작 그대로 (로그인·온보딩 화면 자체가 안 뜸)
deploy=true  → createClient(supabase_url, anon_key) → 세션 구독(onAuthStateChange)
               세션 없음 → /login
               세션 있음 → GET /api/labs/me →
                 lab=null → /onboarding
                 lab 있음 → 앱 라우트 + 사이드바에 연구실 이름·역할
```

컨텍스트 값: `{ mode: "local"|"deploy", session, lab, role, refreshLab() }`.
라우트 가드는 App.tsx에서 컨텍스트 하나로 분기 — 페이지 컴포넌트는 무변경.
`/api/config` 호출(useLogLoop 등)은 가드 안쪽에서만 일어나므로 자연 충족.

## 화면

### /login
- 카드 하나: LAB GENE 로고 + "구글로 계속하기" 버튼 →
  `supabase.auth.signInWithOAuth({ provider: "google" })` (리다이렉트 복귀 후
  onAuthStateChange가 세션 감지). 에러는 카드 안 한 줄.

### /onboarding
- 두 카드: "연구실 만들기"(이름 입력 → POST /api/labs) /
  "초대 코드로 합류"(코드 입력 → POST /api/labs/join).
- 성공 → refreshLab() → 홈. 404(코드 오류)·409(이미 소속) detail 그대로 표시.
- 로그아웃 링크 (다른 계정으로 로그인하고 싶을 때).

### /settings (admin만 — 사이드바에 role==="admin"일 때만 노출)
- 연구실 이름 수정, 초대 코드 표시 + "재발급"(rotate_invite → refreshLab),
  일일 상한 수정, 오늘 사용량/상한 게이지(usage_today 반영 전 "—"),
  멤버 목록(members 반영 전 "—"),
  LLM 모드: 중앙(기본) ↔ 자기 크레덴셜(provider 선택 claude|api + 크레덴셜
  입력 → 저장 시에만 전송, 저장된 값은 다시 안 보여줌).
- 전부 PUT /api/labs/settings 한 번에 저장(변경 필드만).

### 사이드바
- 하단에 연구실 이름 + 내 역할 배지 + 로그아웃 버튼 (deploy 모드에서만).

## API 클라이언트 개조 (api.ts)

- `http()`: deploy 모드면 `supabase.auth.getSession()`의 access token을
  `Authorization: Bearer`로 첨부.
- 401 → `supabase.auth.signOut()` 후 /login 이동. 403(무소속) → /onboarding 이동.
  429·기타 → detail 메시지로 throw (기존 에러 표시 경로).
- 이동은 전역 콜백(AuthProvider가 등록)으로 — api.ts가 라우터를 직접 알지 않게.

## 테스트

- 가드 분기 순수 함수 `resolveRoute(mode, session, lab): "login"|"onboarding"|"app"`
  — vitest 4케이스 (무인증/미로그인/무소속/정상).
- Login·Onboarding·Settings 렌더 테스트 각 1개 (Supabase 클라이언트 모킹).
- 실동작(구글 리다이렉트 왕복)은 스테이징 수동 1회 — 백엔드 auth-config 반영 후.

## 구현 순서

1. auth-config 요청서를 백엔드 세션에 전달 (1번이 블로커)
2. 프론트: origin/main을 frontend에 머지 → AuthProvider·가드·화면 구현
   (auth-config 반영 전엔 로컬 무인증 모드로만 동작 확인 가능)
3. 스테이징에서 구글 로그인 E2E 수동 확인

## 제외 (YAGNI)

이메일/비번 로그인·가입·비번 재설정 UI, 다중 연구실 전환 UI, 멤버 강퇴/역할 변경,
사용량 그래프, 세션 만료 사전 알림 (Supabase SDK가 자동 갱신).
