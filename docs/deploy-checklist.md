# 배포 체크리스트 (Supabase + 구글 로그인 + Railway)

로컬 모드는 이 문서와 무관하다. `SUPABASE_URL`이 없으면 서버는 지금처럼 인증 없이 뜬다.
아래는 **배포 모드**를 켜기 위해 대시보드에서 사람이 해야 하는 작업이다. 순서대로 진행한다.

---

## 1. Supabase 프로젝트 생성 · 키 확보

1. https://supabase.com → **New project**. 이름은 아무거나(`labgene`), 리전은 **Northeast Asia (Seoul)**,
   DB 비밀번호는 생성해서 따로 보관(이후 직접 쓸 일은 없다).
2. 프로젝트가 뜨면 좌측 하단 **Project Settings** 에서 값 4개를 복사해 메모장에 모아둔다.

| 값 | 위치 | 나중에 쓸 환경변수 |
|---|---|---|
| Project URL | Settings → **API** → Project URL | `SUPABASE_URL` |
| anon public key | Settings → **API Keys** → `anon` `public` | `SUPABASE_ANON_KEY` |
| service_role key | 같은 화면 → `service_role` (Reveal 클릭) | `SUPABASE_SERVICE_KEY` |
| JWT Secret | Settings → **JWT Keys** → JWT Secret (Reveal) | `SUPABASE_JWT_SECRET` |

> `service_role` 키와 JWT Secret은 **절대 프론트·깃에 넣지 않는다.** 서버 환경변수 전용이다.
> `anon` 키는 브라우저에 노출되는 것이 전제인 공개 값이라 `/api/auth-config`로 내려간다.

---

## 2. 구글 OAuth 클라이언트 만들기

1. https://console.cloud.google.com → 프로젝트 선택(없으면 새로 만들기).
2. **APIs & Services → OAuth consent screen**
   - User Type: **External** → 만들기
   - 앱 이름 `LAB GENE`, 지원 이메일·개발자 이메일: 본인 이메일
   - Scopes는 기본값 그대로 저장 (email·profile이면 충분)
   - Test users에 파일럿 참여자 구글 계정을 추가 (게시 전에는 등록된 계정만 로그인된다)
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Web application**
   - **Authorized redirect URIs** 에 아래 한 줄을 추가 (`<프로젝트ref>`는 1번의 Project URL에서 따온다):
     ```
     https://<프로젝트ref>.supabase.co/auth/v1/callback
     ```
   - 만들면 나오는 **Client ID / Client secret** 을 복사해둔다.

---

## 3. Supabase에 구글 연결 + 복귀 주소 등록

1. Supabase → **Authentication → Sign In / Providers → Google**
   - Enable 켜고 2번에서 받은 Client ID·Client Secret 붙여넣기 → Save
2. Supabase → **Authentication → URL Configuration**
   - **Site URL**: 배포 도메인 (예: `https://labgene.up.railway.app`). 아직 없으면 `http://localhost:8765`로 두고 6번에서 바꾼다.
   - **Redirect URLs** 에 두 줄 추가:
     ```
     http://localhost:8765
     https://<Railway 도메인>
     ```
   두 곳 다 등록해야 로컬 검증과 실서비스가 같이 동작한다.

---

## 4. 테이블 만들기

Supabase → **SQL Editor → New query** 에 이 저장소의 [`db/schema.sql`](../db/schema.sql) 내용을
그대로 붙여넣고 **Run**. `labs` / `lab_members` / `llm_usage` 3개 테이블이 생기면 끝이다.
(서버는 `service_role` 키로 접근하므로 RLS 정책은 지금 단계에서 필요 없다.)

이어서 **백업 버킷**을 만든다. Supabase → **Storage → New bucket**,
이름은 정확히 `vault-backups`, **Public 은 끈 채로**(볼트 원문이 들어간다) 생성.

서버는 기동 60초 뒤와 이후 24시간마다 볼트 전체를 zip으로 이 버킷에 올린다
(`src/horcrux/backup.py`). 버킷이 없으면 서비스는 정상 동작하지만 백업만 조용히
실패하고 서버 로그에 `(백업 실패 — 다음 주기 재시도: ...)` 가 찍힌다.

---

## 5. 로컬에서 배포 모드로 검증 (여기까지가 이번 작업의 끝선)

배포 모드는 `supabase` 파이썬 패키지를 쓴다. 기본 설치에는 빠져 있으니 먼저 넣는다.
**실행 중인 `horcrux serve`가 있으면 먼저 끄고** (켜져 있으면 실행 파일이 잠겨 설치가 깨진다):

```bash
pip install -e ".[dev,deploy]"
```

암호화 키를 만든다. PowerShell에서:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

출력된 문자열이 `CRED_ENCRYPTION_KEY`다. 연구실이 자기 LLM 크레덴셜을 등록할 때 이 키로 암호화한다.
**이 키를 잃어버리면 등록된 크레덴셜을 복호화할 수 없다** — 실배포 값과 같은 키를 쓰고 따로 보관한다.

같은 PowerShell 창에서 값을 채워 실행한다:

```bash
$env:SUPABASE_URL         = "https://<프로젝트ref>.supabase.co"
$env:SUPABASE_ANON_KEY    = "<anon public key>"
$env:SUPABASE_SERVICE_KEY = "<service_role key>"
$env:SUPABASE_JWT_SECRET  = "<JWT Secret>"
$env:CRED_ENCRYPTION_KEY  = "<위에서 생성한 Fernet 키>"
$env:ANTHROPIC_API_KEY    = "<중앙 API 키>"
$env:DATA_DIR             = "C:\Users\<사용자>\labgene-data"
horcrux serve
```

`ANTHROPIC_API_KEY`는 중앙(central) 모드 연구실이 쓰는 키다. 연구실이 설정에서
"연구실 크레덴셜"로 바꾸면 그 연구실만 자기 토큰을 쓴다.

브라우저에서 http://localhost:8765 를 열고 확인할 것:

- [ ] 로그인 카드가 뜬다 (앱 화면이 바로 뜨면 env가 안 먹은 것 — 위 창에서 그대로 실행했는지 확인)
- [ ] "구글로 계속하기" → 구글 계정 선택 → 앱으로 복귀
- [ ] 연구실 만들기 → 이름 입력 → 홈 화면 진입, 사이드바 하단에 연구실 이름·"관리자" 표시
- [ ] 실험 로그 하나 기록 → 저장 성공, `DATA_DIR\vaults\<lab-id>\raw\experiments\` 에 md 생성
- [ ] 연구노트에서 참고문헌 추가 → 새로고침 후에도 남아 있음
- [ ] 사이드바 "⚙ 연구실 설정" → 초대 코드 보임, 재발급 동작, 오늘 사용량 표시
- [ ] 로그아웃 → 로그인 카드로 복귀

다른 구글 계정으로 초대 코드 합류까지 확인하면 더 좋다(멤버는 설정 링크가 안 보여야 정상).

---

## 6. Railway 배포

1. https://railway.app → **New Project → Deploy from GitHub repo** → 이 저장소 선택.
   루트의 `Dockerfile`을 자동으로 감지한다.
2. **Variables** 에 5번의 환경변수를 그대로 입력한다. 단 `DATA_DIR`은 `/data`.
3. **Settings → Volumes → New Volume**, Mount path `/data`.
   (볼륨이 없으면 재배포마다 볼트가 통째로 사라진다.)
4. **Settings → Networking → Generate Domain** 으로 도메인을 받고,
   그 주소를 3번의 Site URL·Redirect URLs에 반영한다.
5. 배포된 주소로 접속해 5번 체크리스트를 한 번 더 훑는다.

백업은 서버가 자동으로 돈다(`src/horcrux/backup.py`). 별도 설정 없음.

---

## 자주 걸리는 곳

| 증상 | 원인 |
|---|---|
| 로그인 화면 없이 앱이 바로 뜬다 | `SUPABASE_URL`이 프로세스에 안 들어감 — 서버를 띄운 그 창에서 env를 설정했는지 확인 |
| 서버 기동 시 `TypeError: 'NoneType' object is not callable` | `supabase` 패키지 미설치 — 5번 맨 위의 `pip install -e ".[dev,deploy]"` |
| 구글 로그인 후 `redirect_uri_mismatch` | 2번의 Authorized redirect URI가 `https://<ref>.supabase.co/auth/v1/callback` 과 정확히 일치하지 않음 |
| 로그인은 되는데 앱이 로그인 화면으로 되돌아옴 | 3번 Redirect URLs에 접속 주소가 없음 |
| 401이 계속 난다 | `SUPABASE_JWT_SECRET`이 다른 프로젝트 값이거나 오타 |
| 연구실 설정 저장 시 502 | own 모드인데 크레덴셜 미등록 — 설정에서 토큰을 다시 입력 |
| 429 "오늘 사용량 한도 초과" | 설정에서 일일 상한을 올리거나 다음 날 대기 |
