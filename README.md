# horcrux

연구실 실험 기록·문제 진단 CLI. 실험 로그를 자연어로 입력하면 LLM이 구조화해
마크다운 볼트(옵시디언 호환)에 저장하고, 문제 질의 시 과거 유사 사례를 검색해
근거와 함께 진단을 보조한다.

## 설치

```
pip install -e .
set HORCRUX_VAULT=example-vault     # 랩 볼트 경로 (연구실 1곳 = 볼트 1개)
set HORCRUX_PROVIDER=claude         # claude | gemini | codex (기본 claude)
set HORCRUX_MODEL=...               # 생략 시 CLI 기본 모델
```

LLM 호출은 API 키 대신 로컬 CLI(subprocess)를 쓴다 — 셋 중 하나가 설치·로그인돼
있으면 된다: `claude`(Claude Code), `gemini`(Gemini CLI), `codex`(Codex CLI).

검색은 LLM-select: LLM이 레코드·위키 카탈로그를 읽고 유사 사례를 직접 고른다.
임베딩·벡터 인덱스 없이 CLI 로그인만으로 동작한다.

## 디스코드 봇

봇 프로세스를 랩서버에 상주시키면 연구원은 디스코드 채널로 기록·질의한다.

### 준비 (1회)

1. [Discord 개발자 포털](https://discord.com/developers/applications) → New Application → Bot 추가
2. **Privileged Gateway Intents에서 Message Content Intent 켜기** (필수)
3. Bot 토큰 발급 → 환경변수 `HORCRUX_DISCORD_TOKEN`으로 설정 (레포·코드에 넣지 말 것)
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
