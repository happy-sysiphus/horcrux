# horcrux

연구실 실험 기록·문제 진단 CLI. 실험 로그를 자연어로 입력하면 LLM이 구조화해
마크다운 볼트(옵시디언 호환)에 저장하고, 문제 질의 시 과거 유사 사례를 검색해
근거와 함께 진단을 보조한다.

## 설치

[GitHub Releases](../../releases)에서 받는다. 두 트랙 중 하나:

**트랙 1 — Python 3.10+ 있음**: `horcrux-<버전>-py3-none-any.whl` 다운로드 후

```
pip install horcrux-<버전>-py3-none-any.whl
```

**트랙 2 — Python 없음 (Windows)**: `horcrux.exe` 다운로드, 아무 폴더에 두고 그 폴더에서 실행.
Windows Defender가 차단하면 [추가 정보 → 실행] 또는 [허용]으로 통과 (서명 없는 exe 오탐).

### 설치 후 공통 절차 (순서대로)

1. **LLM CLI 설치·로그인** — 셋 중 하나: `claude`(Claude Code) / `gemini`(Gemini CLI) /
   `codex`(Codex CLI). Horcrux는 API 키 대신 로컬 CLI를 subprocess로 호출한다.
2. **디스코드 봇 계정 생성·서버 초대** — 아래 "디스코드 봇 > 준비" 참조.
3. **설정 마법사**:

```
horcrux init
```

토큰·볼트 절대경로·provider·채널명을 물어 `~/.horcrux/config.yaml`에 저장한다.
(환경변수 `HORCRUX_*`가 설정돼 있으면 그게 파일보다 우선. 토큰은 평문 저장 —
유출 시 개발자 포털에서 Reset Token.)

4. **실행**:

```
horcrux bot
```

봇은 이 프로세스가 켜져 있는 동안만 응답한다. 재부팅 후 자동 시작하려면:
`horcrux bot` 한 줄짜리 `horcrux.bat`을 만들어 `Win+R` → `shell:startup` 폴더에 넣는다.

### 개발 설치

```
git clone <repo> && cd horcrux
pip install -e .[dev]
```

검색은 LLM-select: LLM이 레코드·위키 카탈로그를 읽고 유사 사례를 직접 고른다.
임베딩·벡터 인덱스 없이 CLI 로그인만으로 동작한다.

## 디스코드 봇

봇 프로세스를 랩서버에 상주시키면 연구원은 디스코드 채널로 기록·질의한다.

### 준비 (1회)

1. [Discord 개발자 포털](https://discord.com/developers/applications) → New Application → Bot 추가
2. **Privileged Gateway Intents에서 Message Content Intent 켜기** (필수)
3. Bot 토큰 발급 → `horcrux init`에서 입력 (또는 환경변수 `HORCRUX_DISCORD_TOKEN`. 레포·코드에 넣지 말 것)
4. OAuth2 → URL Generator에서 `bot` 스코프 + 권한(View Channels, Send Messages, Read Message History) 체크 → 생성된 URL로 서버에 초대
5. 서버에 텍스트 채널 `실험로그`, `질문` 생성 (이름 변경 시 `HORCRUX_LOG_CHANNEL`/`HORCRUX_ASK_CHANNEL`)

### 실행

```bash
horcrux bot
```

- `#실험로그`에 자연어 로그를 쓰면 구조화 저장 (부족 정보는 봇이 되물음 — 10분 무응답 시 그대로 저장)
- 사진 등 첨부는 볼트 `raw/attachments/<레코드id>/`에 저장되고 기록 본문에 링크됨 (이미지 내용 분석은 안 함. 파싱 실패 needs_review 레코드는 폴더에만 저장되고 본문 링크 없음)
- `#질문`에 문제를 쓰면 과거 사례·위키 기반 진단
- `/feedback` `/absorb` `/seed` 슬래시 커맨드 지원
- 랩서버에도 선택한 LLM CLI(claude 등)가 설치·로그인돼 있어야 한다

## 사용

```
horcrux seed          # 합성 데모 데이터 생성 + 위키 편찬 (개발용)
horcrux log           # 실험 로그 기록 (부족 정보 되물음, 저장 후 위키 자동 편찬)
horcrux ask           # 문제 질의 (과거 유사 사례·위키 근거로 답변)
horcrux absorb        # 위키 재편찬 (log/seed가 자동 실행 — 실패 시 재시도용)
horcrux feedback <id> --resolved y --cause "타겟 산화"   # 결과 피드백
```

## 연구실 설정 (§2a)

볼트에 `config.yaml`을 두면 기록 시 하드 게이트가 적용된다 (없으면 5개 카테고리 전부 기본):

```
required_fields: [objective, parameters, results, symptom, actions_taken]
required_parameters:
  - 기판 온도
  - 챔버 습도
```

설계 문서: `docs/superpowers/specs/2026-07-19-horcrux-mvp-design.md`
