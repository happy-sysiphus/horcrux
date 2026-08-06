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
2. **설정 마법사**:

```
horcrux init
```

볼트 절대경로·provider·모델을 물어 `~/.horcrux/config.yaml`에 저장한다.
(환경변수 `HORCRUX_*`가 설정돼 있으면 그게 파일보다 우선.)

3. **실행** — 아래 "웹 UI (LAB GENE)" 참조.

### 개발 설치

```
git clone <repo> && cd horcrux
pip install -e .[dev]
```

검색은 LLM-select: LLM이 레코드·위키 카탈로그를 읽고 유사 사례를 직접 고른다.
임베딩·벡터 인덱스 없이 CLI 로그인만으로 동작한다.

## 사용

```
horcrux seed          # 합성 데모 데이터 생성 + 위키 편찬 (개발용)
horcrux log           # 실험 로그 기록 (부족 정보 되물음, 저장 후 위키 자동 편찬)
horcrux ask           # 문제 질의 (과거 유사 사례·위키 근거로 답변)
horcrux absorb        # 위키 재편찬 (log/seed가 자동 실행 — 실패 시 재시도용)
horcrux feedback <id> --resolved y --cause "타겟 산화"   # 결과 피드백
horcrux serve         # 웹 UI (LAB GENE) — http://127.0.0.1:8765
```

## 웹 UI (LAB GENE)

    pip install -e ".[web]"
    cd web && npm install && npm run build && cd ..
    horcrux serve

브라우저에서 http://127.0.0.1:8765 접속. 기록/질문/연구노트/실험 피드백/후속 실험을
브라우저에서 수행한다 (CLI와 같은 볼트 공유).
개발 모드: `horcrux serve` + `cd web && npm run dev` (vite가 /api 프록시).

## 연구실 설정 (§2a)

볼트에 `config.yaml`을 두면 기록 시 하드 게이트가 적용된다 (없으면 6개 카테고리 전부 기본):

```
required_fields: [objective, parameters, results, symptom, actions_taken, notes]
required_parameters:
  - 기판 온도
  - 챔버 습도
```

공정변수는 단위 포함이 필수다 — 단위 없이 기록하면 재질문한다 (횟수·비율 등 무차원 값 예외).

설계 문서: `docs/superpowers/specs/2026-07-19-horcrux-mvp-design.md`
