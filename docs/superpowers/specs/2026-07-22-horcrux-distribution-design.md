# Horcrux 배포(셀프호스팅 패키징) — 설계

날짜: 2026-07-22
상태: 승인됨 (접근안 A: 로컬 빌드 + 수동 릴리스)

## 목적

다른 연구실이 "패키지 파일 설치하면 돌아가는" 수준으로 Horcrux를 배포한다.
모델은 **셀프호스팅**: 각 연구실이 패키지를 설치하고, 자기 디스코드 봇 계정(토큰)을
만들고, 자기 머신에서 `horcrux bot`을 돌린다. 데이터(볼트)와 LLM 비용(CLI 구독)은
설치처 부담 — 중앙 호스팅(봇 하나가 여러 길드) 아님.

바뀌지 않는 전제: LLM CLI(claude/gemini/codex)는 번들 불가 — 설치처가 별도
설치·로그인해야 한다. 배포물이 줄여주는 건 그 외 전부다.

## 설정 계층 + `horcrux init`

**프로그램 설정 파일** `~/.horcrux/config.yaml` (볼트 안 `config.yaml`
= 연구실 게이트 설정과 별개 — 문서에 구분 명시):

```yaml
discord_token: "..."
vault: C:/lab/horcrux-vault    # 절대경로 권장 — cwd 의존 제거
provider: claude               # claude | gemini | codex
model:                         # 비우면 CLI 기본 모델
log_channel: 실험로그
ask_channel: 질문
```

**우선순위: 환경변수 > 설정파일 > 기본값** — 기존 env var 사용자 호환 유지.
env var: `HORCRUX_DISCORD_TOKEN`/`HORCRUX_VAULT`/`HORCRUX_PROVIDER`/`HORCRUX_MODEL`/
`HORCRUX_LOG_CHANNEL`/`HORCRUX_ASK_CHANNEL`.

**구조 변경**:
- `Config`에 `discord_token: str | None`, `log_channel: str = "실험로그"`,
  `ask_channel: str = "질문"` 필드 추가. `load_config()`가 설정파일을 읽고 env로
  오버라이드 (config.py — 백엔드).
- `bot.py`의 직접 `os.environ` 읽기(토큰·채널명) 제거 — 전부 `cfg` 경유.
  인터페이스 계약의 Config 확장이므로 레이어 경계 유지.
- `horcrux init` (cli.py): 대화형으로 토큰·볼트 절대경로·provider·채널명 입력 →
  파일 생성. 기존 파일 있으면 현재값을 기본값으로 표시, 빈 입력 = 유지.
  완료 시 다음 단계("horcrux bot 실행") 안내. 토큰 유효성 검증은 안 함
  (실행 시 로그인 실패로 드러남 — YAGNI).

## 빌드·릴리스 (접근안 A)

- 버전 `0.2.0` (봇 + 배포 기능 포함 첫 릴리스).
- `src/horcrux/__main__.py` 신규 (2줄) — `python -m horcrux` 지원 + PyInstaller 엔트리.
- `scripts/build_release.py` 하나:
  1. `python -m build --wheel` → `dist/horcrux-<ver>-py3-none-any.whl`
  2. PyInstaller `--onefile --name horcrux` → `dist/horcrux.exe`
  3. 자체 검증: 빌드된 exe로 `--help` 실행 확인
- 릴리스 절차는 `docs/RELEASING.md` (수동 5줄): 태그 `v<ver>` 푸시 → GitHub
  Releases 생성 → whl + exe 첨부.
- 채널은 GitHub Releases만 (PyPI 안 씀 — 계정·패키지명 선점 문제 회피).

## 설치 문서 (README 설치 섹션 재작성)

- **트랙 1 (Python 3.10+ 있음)**: Releases에서 whl 다운로드 →
  `pip install horcrux-<ver>-py3-none-any.whl`
- **트랙 2 (Python 없음)**: `horcrux.exe` 다운로드, 아무 폴더에 두고 실행.
  Windows Defender 오탐 시 허용 처리 안내 포함.
- **공통 후속 절차** (순서대로): ① LLM CLI 설치·로그인(별도 소단원 — 제일 큰 외부
  의존) ② 디스코드 봇 계정 생성·Message Content Intent·서버 초대(기존 봇 단원 참조)
  ③ `horcrux init` ④ `horcrux bot`
- **상주**: 수동 실행 기본. 재부팅 자동 시작은 시작프로그램에 bat 등록법 3줄 안내
  (코드 추가 없음).

## 테스트

- `load_config` 우선순위: 파일만 / env 오버라이드 / 둘 다 없음 기본값 —
  기존 monkeypatch 패턴.
- init: `input` 모킹 → 파일 생성 내용 확인, 기존 파일 있을 때 빈 입력 = 기존값 유지.
- bot 채널명·토큰이 cfg 경유로 바뀐 뒤에도 기존 bot 테스트 전부 통과.
- exe는 자동화 안 함 — 릴리스 절차에 수동 스모크(`--help`·`init`·`bot` 기동) 포함.

## 보안 노트

- 토큰은 홈 디렉터리 평문 저장 — 로컬 단일 사용자 관행 수용, README에 명시
  ("토큰 유출 시 개발자 포털에서 Reset").
- exe는 코드 서명 없음 — Defender 오탐 가능, 문서로 대응.

## 제외 (YAGNI)

PyPI 배포, GitHub Actions 자동 릴리스, 코드 서명, 자동 업데이트, macOS/Linux
바이너리(whl은 크로스플랫폼이라 pip 트랙으로 커버), 토큰 암호화 저장, 중앙 호스팅
(길드별 볼트 매핑), 자동 시작 등록 명령.
