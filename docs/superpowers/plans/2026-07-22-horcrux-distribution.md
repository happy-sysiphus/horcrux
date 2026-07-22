# Horcrux 배포(셀프호스팅 패키징) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 설정 계층(`~/.horcrux/config.yaml` + `horcrux init`) + whl/exe 빌드·릴리스 절차로 "설치하면 돌아가는" 배포물 완성.

**Architecture:** config.py가 설정파일→env 병합을 담당(우선순위: env > 파일 > 기본값), bot.py는 env 직접 읽기를 버리고 전부 cfg 경유. 빌드는 로컬 스크립트 하나(whl + PyInstaller exe), 릴리스는 GitHub Releases 수동.

**Tech Stack:** Python 3.10+, pyyaml(기존 의존성), build, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-07-22-horcrux-distribution-design.md`

## Global Constraints

- pytest 실행은 반드시 `python -m pytest -q --basetemp=.pytest_tmp` (샌드박스 temp 권한 문제).
- 테스트에서 LLM·네트워크 호출 금지. 설정 테스트는 반드시 `_config_path`를 tmp로 격리 — 실행 머신의 실제 `~/.horcrux/config.yaml`을 읽으면 안 됨.
- 우선순위 불변식: **환경변수 > 설정파일 > 기본값**. env var 6종: `HORCRUX_DISCORD_TOKEN`/`HORCRUX_VAULT`/`HORCRUX_PROVIDER`/`HORCRUX_MODEL`/`HORCRUX_LOG_CHANNEL`/`HORCRUX_ASK_CHANNEL`.
- 기본값 불변: vault `example-vault`, provider `claude`, log 채널 `실험로그`, ask 채널 `질문`.
- 버전 `0.2.0`. 커밋 스타일 `feat:`/`docs:`/`chore:` + 한국어.
- 구현은 워크트리에서 (기존 `bot-impl` 워크트리 재사용 가능 — 시작 시 `git merge main`으로 최신화).

---

### Task 1: 설정 계층 — 파일 로드·병합 + save_config

**Files:**
- Modify: `src/horcrux/config.py`
- Create: `tests/conftest.py` (전 스위트 공용 격리 fixture)
- Test: `tests/test_llm.py` (기존 load_config 테스트 2개 교체 + 신규 5개)

**Interfaces:**
- Produces: `Config` 필드 추가 — `discord_token: str | None = None`, `log_channel: str = "실험로그"`, `ask_channel: str = "질문"`. `_config_path() -> Path` (모듈 함수 — 테스트가 monkeypatch), `load_config() -> Config` (파일+env 병합), `save_config(values: dict) -> Path` (yaml 저장, 부모 디렉터리 생성).

- [ ] **Step 1: 공용 격리 fixture + 실패 테스트**

`tests/conftest.py` 생성 — **autouse**라 스위트 전체(기존 test_cli의 main() 호출 포함)가 실행 머신의 실제 `~/.horcrux/config.yaml`·`HORCRUX_*` env를 절대 읽지 않게 된다:

```python
import pytest

ALL_ENV = ("HORCRUX_VAULT", "HORCRUX_PROVIDER", "HORCRUX_MODEL",
           "HORCRUX_DISCORD_TOKEN", "HORCRUX_LOG_CHANNEL", "HORCRUX_ASK_CHANNEL")


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    # 모든 테스트에서 실제 ~/.horcrux/config.yaml·HORCRUX_* env 격리.
    # raising=False: Task 1 구현 전(_config_path 부재)에도 기존 테스트가 안 깨지게.
    from horcrux import config as config_mod
    p = tmp_path / "config.yaml"
    monkeypatch.setattr(config_mod, "_config_path", lambda: p, raising=False)
    for k in ALL_ENV:
        monkeypatch.delenv(k, raising=False)
    return p
```

`tests/test_llm.py`의 `test_load_config_defaults`와 `test_load_config_env_override` 두 개를 아래로 교체하고, 그 아래 신규 테스트 5개를 추가 (파일 상단 import에 `import yaml`, `from pathlib import Path` 없으면 추가). `isolated_config`는 conftest 것을 파라미터로 받는다:

```python
def test_load_config_defaults(isolated_config):
    cfg = load_config()
    assert cfg.provider == "claude"
    assert cfg.model is None
    assert str(cfg.vault) == "example-vault"
    assert cfg.discord_token is None
    assert cfg.log_channel == "실험로그"
    assert cfg.ask_channel == "질문"


def test_load_config_env_override(isolated_config, monkeypatch):
    monkeypatch.setenv("HORCRUX_VAULT", "my-lab")
    monkeypatch.setenv("HORCRUX_PROVIDER", "gemini")
    monkeypatch.setenv("HORCRUX_MODEL", "gemini-2.5-pro")
    cfg = load_config()
    assert str(cfg.vault) == "my-lab"
    assert cfg.provider == "gemini"
    assert cfg.model == "gemini-2.5-pro"


def test_load_config_from_file(isolated_config):
    isolated_config.write_text(yaml.safe_dump({
        "discord_token": "tok", "vault": "C:/lab/v", "provider": "codex",
        "log_channel": "lab-log",
    }, allow_unicode=True), encoding="utf-8")
    cfg = load_config()
    assert cfg.discord_token == "tok"
    assert cfg.vault == Path("C:/lab/v")
    assert cfg.provider == "codex"
    assert cfg.log_channel == "lab-log"
    assert cfg.ask_channel == "질문"  # 파일에 없는 키는 기본값


def test_env_beats_file(isolated_config, monkeypatch):
    isolated_config.write_text(yaml.safe_dump({"provider": "codex"}), encoding="utf-8")
    monkeypatch.setenv("HORCRUX_PROVIDER", "claude")
    assert load_config().provider == "claude"


def test_save_config_roundtrip(isolated_config):
    from horcrux.config import save_config
    path = save_config({"discord_token": "t", "vault": "C:/v", "provider": "claude",
                        "model": None, "log_channel": "실험로그", "ask_channel": "질문"})
    assert path == isolated_config
    cfg = load_config()
    assert cfg.discord_token == "t" and cfg.vault == Path("C:/v")


def test_save_config_creates_parent_dir(monkeypatch, tmp_path):
    from horcrux import config as config_mod
    p = tmp_path / "deep" / "config.yaml"
    monkeypatch.setattr(config_mod, "_config_path", lambda: p, raising=False)
    from horcrux.config import save_config
    save_config({"provider": "claude"})
    assert p.exists()


def test_load_config_ignores_corrupt_file(isolated_config):
    isolated_config.write_text("그냥 문자열", encoding="utf-8")  # dict 아닌 YAML
    assert load_config().provider == "claude"  # 트레이스백 없이 기본값
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_llm.py`
Expected: 교체 2개 + 신규 5개 FAIL — `cfg.discord_token` AttributeError, `save_config` ImportError. (conftest는 raising=False라 기존 다른 테스트는 통과.)

- [ ] **Step 3: 구현**

`src/horcrux/config.py`의 `Config`와 `load_config`를 아래로 교체하고 `_config_path`/`save_config` 추가:

```python
@dataclass
class Config:
    vault: Path
    provider: str = "claude"
    model: str | None = None  # None = 각 CLI의 기본 모델 사용
    discord_token: str | None = None
    log_channel: str = "실험로그"
    ask_channel: str = "질문"

    def __post_init__(self):
        self.vault = Path(self.vault)


def _config_path() -> Path:
    # 프로그램 설정 — 볼트의 config.yaml(연구실 게이트 설정)과 별개
    return Path.home() / ".horcrux" / "config.yaml"


def load_config() -> Config:
    data = {}
    p = _config_path()
    if p.exists():
        import yaml
        loaded = yaml.safe_load(p.read_text(encoding="utf-8"))
        data = loaded if isinstance(loaded, dict) else {}  # 깨진 파일은 무시 — init으로 재작성

    def pick(env_key: str, file_key: str, default):
        return os.environ.get(env_key) or data.get(file_key) or default

    return Config(
        vault=Path(pick("HORCRUX_VAULT", "vault", "example-vault")),
        provider=pick("HORCRUX_PROVIDER", "provider", "claude"),
        model=pick("HORCRUX_MODEL", "model", None),
        discord_token=pick("HORCRUX_DISCORD_TOKEN", "discord_token", None),
        log_channel=pick("HORCRUX_LOG_CHANNEL", "log_channel", "실험로그"),
        ask_channel=pick("HORCRUX_ASK_CHANNEL", "ask_channel", "질문"),
    )


def save_config(values: dict) -> Path:
    import yaml
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(values, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_llm.py`
Expected: PASS 전부.

- [ ] **Step 5: 전체 회귀 + Commit**

Run: `python -m pytest -q --basetemp=.pytest_tmp` → 전부 PASS.

```bash
git add src/horcrux/config.py tests/test_llm.py
git commit -m "feat: 설정파일(~/.horcrux/config.yaml) 계층 — env > 파일 > 기본값"
```

---

### Task 2: bot.py를 cfg 경유로 — env 직접 읽기 제거

**Files:**
- Modify: `src/horcrux/bot.py` (`HorcruxBot.__init__`의 채널, `run_bot`의 토큰)
- Test: `tests/test_bot.py` (신규 1개)

**Interfaces:**
- Consumes: Task 1의 `Config.discord_token`/`log_channel`/`ask_channel`.
- Produces: `run_bot(cfg)` — `cfg.discord_token` 없으면 RuntimeError(메시지에 `HORCRUX_DISCORD_TOKEN`과 `horcrux init` 언급). `HorcruxBot.log_channel`/`ask_channel`은 cfg에서 옴.

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_bot.py` 끝에 추가:

```python
def test_build_client_channels_from_cfg(tmp_path):
    c = bot.build_client(Config(vault=tmp_path, log_channel="lab-log", ask_channel="lab-ask"))
    assert (c.log_channel, c.ask_channel) == ("lab-log", "lab-ask")
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_bot.py::test_build_client_channels_from_cfg`
Expected: FAIL — 현재는 env에서 읽어 기본값 `실험로그`/`질문`이 나옴.

- [ ] **Step 3: 구현**

`src/horcrux/bot.py`의 `HorcruxBot.__init__`에서 채널 두 줄을 교체:

```python
        self.log_channel = cfg.log_channel
        self.ask_channel = cfg.ask_channel
```

`run_bot`을 교체:

```python
def run_bot(cfg: Config) -> None:
    if not cfg.discord_token:
        raise RuntimeError(
            "봇 토큰 미설정 — 'horcrux init'으로 설정하거나 HORCRUX_DISCORD_TOKEN 환경변수를 넣어주세요")
    build_client(cfg).run(cfg.discord_token)
```

`os` import는 `save_attachments`가 계속 쓰므로 유지.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_bot.py`
Expected: PASS 전부 (기존 `test_run_bot_without_token_raises`는 메시지에 `HORCRUX_DISCORD_TOKEN`이 남아 있어 그대로 통과).

- [ ] **Step 5: Commit**

```bash
git add src/horcrux/bot.py tests/test_bot.py
git commit -m "feat: 봇 설정을 cfg 경유로 — env 직접 읽기 제거"
```

---

### Task 3: `horcrux init` 대화형 마법사

**Files:**
- Modify: `src/horcrux/cli.py`
- Test: `tests/test_cli.py` (신규 2개)

**Interfaces:**
- Consumes: Task 1의 `load_config()`/`save_config(values) -> Path`.
- Produces: `cli.run_init() -> None`, `horcrux init` 서브커맨드.

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_cli.py` 끝에 추가 (상단 import에 `import yaml` 없으면 추가):

격리는 `tests/conftest.py`의 autouse `isolated_config`(Task 1)가 이미 해준다 — 파라미터로 받기만 하면 됨:

```python
def test_cli_init_writes_config(monkeypatch, isolated_config):
    answers = iter(["tok-1", "C:/lab/vault", "gemini", "", "lab-log", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    from horcrux.cli import main
    main(["init"])
    data = yaml.safe_load(isolated_config.read_text(encoding="utf-8"))
    assert data["discord_token"] == "tok-1"
    assert data["vault"] == "C:/lab/vault"
    assert data["provider"] == "gemini"
    assert data["model"] is None          # 빈 입력 + 기존값 없음 = None
    assert data["log_channel"] == "lab-log"
    assert data["ask_channel"] == "질문"   # 빈 입력 = 기본값 유지


def test_cli_init_keeps_existing_on_empty(monkeypatch, isolated_config):
    isolated_config.write_text(yaml.safe_dump({
        "discord_token": "tok-old", "vault": "C:/old", "provider": "codex",
        "model": "o3", "log_channel": "L", "ask_channel": "A",
    }, allow_unicode=True), encoding="utf-8")
    answers = iter(["", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    from horcrux.cli import main
    main(["init"])
    data = yaml.safe_load(isolated_config.read_text(encoding="utf-8"))
    assert data == {"discord_token": "tok-old", "vault": "C:/old", "provider": "codex",
                    "model": "o3", "log_channel": "L", "ask_channel": "A"}
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_cli.py`
Expected: 신규 2개 FAIL — `init` 서브커맨드 없어 argparse SystemExit(2).

- [ ] **Step 3: 구현**

`src/horcrux/cli.py`에 함수 추가 (`main` 위):

```python
def run_init() -> None:
    from .config import load_config, save_config
    cur = load_config()  # 기존 파일+env 반영값을 기본값으로 보여줌
    print("Horcrux 설정 — 빈 입력은 [현재값] 유지")

    def ask(label: str, cur_val) -> str:
        raw = input(f"{label} [{cur_val or ''}]: ").strip()
        return raw or (str(cur_val) if cur_val else "")

    token = ask("디스코드 봇 토큰", cur.discord_token)
    vault = ask("볼트 절대경로", cur.vault)
    provider = ask("LLM provider (claude/gemini/codex)", cur.provider)
    model = ask("모델 (빈 값 = CLI 기본)", cur.model)
    log_ch = ask("log 채널 이름", cur.log_channel)
    ask_ch = ask("ask 채널 이름", cur.ask_channel)
    path = save_config({
        "discord_token": token or None, "vault": vault, "provider": provider,
        "model": model or None, "log_channel": log_ch, "ask_channel": ask_ch,
    })
    print(f"저장됨: {path}")
    print("다음: 'horcrux bot' 실행 (LLM CLI 로그인·봇 서버 초대는 README 참조)")
```

`main`에 서브파서 추가 (`bot` 파서 아래):

```python
    sub.add_parser("init", help="설정 마법사 (~/.horcrux/config.yaml 생성)")
```

**분기는 `cfg = load_config()` 앞에** — 설정파일이 깨져 있어도 그걸 고칠 마법사는 떠야 한다:

```python
    args = p.parse_args(argv)
    if args.cmd == "init":
        run_init()  # cfg 로드 전 분기 — 깨진 설정파일도 init으로 복구 가능해야 함
        return
    cfg = load_config()
```

(기존 `cfg = load_config()` 줄을 위 형태로 교체. `elif args.cmd == "init"` 분기는 만들지 않는다.)

주의: `cur.vault`는 Path — `ask`가 `str(cur_val)`로 문자열화하므로 저장값은 문자열. `test_cli_init_keeps_existing_on_empty`에서 vault `"C:/old"` → `Path("C:/old")` → `str()` → `"C:\\old"`가 되면 assert 실패한다. **Windows에서 `str(Path("C:/old")) == "C:\\old"`이므로**, `ask("볼트 절대경로", cur.vault)` 호출은 `cur.vault`를 그대로 넘기지 말고 `cur.vault.as_posix()`를 넘겨라:

```python
    vault = ask("볼트 절대경로", cur.vault.as_posix())
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_cli.py`
Expected: PASS 전부.

- [ ] **Step 5: 전체 회귀 + Commit**

Run: `python -m pytest -q --basetemp=.pytest_tmp` → 전부 PASS.

```bash
git add src/horcrux/cli.py tests/test_cli.py
git commit -m "feat: horcrux init 설정 마법사"
```

---

### Task 4: 패키징 — 버전·__main__·빌드 스크립트·릴리스 절차

**Files:**
- Modify: `pyproject.toml` (version 0.2.0, [release] extra)
- Create: `src/horcrux/__main__.py`
- Create: `scripts/build_release.py`
- Create: `docs/RELEASING.md`

**Interfaces:**
- Consumes: `horcrux.cli.main`.
- Produces: `python -m horcrux` 동작, `python scripts/build_release.py` → `dist/horcrux-0.2.0-py3-none-any.whl` + `dist/horcrux.exe`.

- [ ] **Step 1: pyproject 수정**

`pyproject.toml`: `version = "0.1.0"` → `version = "0.2.0"`. `[project.optional-dependencies]`에 추가:

```toml
release = ["build", "pyinstaller"]
```

- [ ] **Step 2: __main__.py 생성**

`src/horcrux/__main__.py`:

```python
from horcrux.cli import main

if __name__ == "__main__":
    main()
```

확인: `python -m horcrux --help` → 사용법 출력.

- [ ] **Step 3: 빌드 스크립트 생성**

`scripts/build_release.py`:

```python
"""whl + exe 빌드 (Windows 전용 — exe 아티팩트명 고정). 릴리스 절차는 docs/RELEASING.md 참조.

사전: pip install -e .[release]
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*cmd: str) -> None:
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


run(sys.executable, "-m", "build", "--wheel")
run(sys.executable, "-m", "PyInstaller", "--onefile", "--noconfirm", "--name", "horcrux",
    "--paths", str(ROOT / "src"),  # editable 설치 여부와 무관하게 horcrux 패키지 해석
    str(ROOT / "src" / "horcrux" / "__main__.py"))
run(str(ROOT / "dist" / "horcrux.exe"), "--help")  # 번들 임포트 자체 검증
print("완료 — dist/ 에 whl + horcrux.exe")
```

- [ ] **Step 4: 빌드 실행 검증**

Run: `pip install -e .[release]` 후 `python scripts/build_release.py`
Expected: `dist/horcrux-0.2.0-py3-none-any.whl`과 `dist/horcrux.exe` 생성, 마지막에 exe `--help` 출력 후 "완료". (수 분 소요.)
트러블슈팅: `ModuleNotFoundError: horcrux`(자기 패키지)는 경로 해석 문제 — `--paths`가 이미 커맨드에 있으니 발생 시 `pip install .`(비-editable)로 재시도. **서드파티** 모듈 누락일 때만 `--hidden-import <그 모듈>` 추가.
`.gitignore`에 `dist/`·`build/`·`horcrux.spec` 세 줄 추가 (현재 없음 — 빌드가 셋 다 리포 루트에 생성함).

- [ ] **Step 5: RELEASING.md 생성**

`docs/RELEASING.md`:

```markdown
# 릴리스 절차 (수동)

1. `pyproject.toml` 버전 올리고 커밋 (`chore: v<ver>`)
2. `pip install -e .[release]` 후 `python scripts/build_release.py` → `dist/` 확인
3. 수동 스모크: `dist/horcrux.exe --help` → `dist/horcrux.exe init`으로 설정 생성 → `dist/horcrux.exe bot` 기동·로그인 확인
4. `git tag v<ver> && git push --tags`
5. GitHub Releases → 새 릴리스(태그 선택) → `dist/horcrux-<ver>-py3-none-any.whl` + `dist/horcrux.exe` 첨부 → 설명에 README 설치 섹션 링크
```

- [ ] **Step 6: 전체 회귀 + Commit**

Run: `python -m pytest -q --basetemp=.pytest_tmp` → 전부 PASS.

```bash
git add pyproject.toml src/horcrux/__main__.py scripts/build_release.py docs/RELEASING.md .gitignore
git commit -m "feat: v0.2.0 패키징 — __main__·빌드 스크립트·릴리스 절차"
```

---

### Task 5: README 설치 섹션 재작성

**Files:**
- Modify: `README.md` (`## 설치` 섹션 교체 + `## 디스코드 봇` 준비 3번 항목 수정)

- [ ] **Step 1: `## 설치` 섹션 교체**

현재 `## 설치`부터 "임베딩·벡터 인덱스 없이 CLI 로그인만으로 동작한다." 줄까지를 아래로 교체:

````markdown
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
````

- [ ] **Step 2: 디스코드 봇 준비 항목 수정**

`## 디스코드 봇 > ### 준비 (1회)`의 3번 항목을 교체:

현재: `3. Bot 토큰 발급 → 환경변수 \`HORCRUX_DISCORD_TOKEN\`으로 설정 (레포·코드에 넣지 말 것)`

교체: `3. Bot 토큰 발급 → \`horcrux init\`에서 입력 (또는 환경변수 \`HORCRUX_DISCORD_TOKEN\`. 레포·코드에 넣지 말 것)`

같은 섹션 5번 항목의 env var 안내는 유지 (env가 파일보다 우선이므로 여전히 유효).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: 설치 2트랙(whl/exe)·init·자동 시작 안내"
```

---

### Task 6: 전체 검증 + 릴리스

**Files:** 없음 (검증·릴리스 절차)

- [ ] **Step 1: 전체 테스트**

Run: `python -m pytest -q --basetemp=.pytest_tmp`
Expected: 전부 PASS (기존 85 + 신규 ≈8 = ≈93).

- [ ] **Step 2: 수동 스모크 (사용자와 함께)**

1. `python -m horcrux --help` 확인
2. `horcrux init` 실제 실행 → `~/.horcrux/config.yaml` 생성 확인 → `horcrux bot` 기동 (env var 없이 파일만으로 로그인되는지)
3. `dist/horcrux.exe --help` + `dist/horcrux.exe bot` 기동 1회

- [ ] **Step 3: 브랜치 마무리 + 릴리스**

superpowers:finishing-a-development-branch로 main 병합 → `docs/RELEASING.md` 절차대로 v0.2.0 태그·GitHub Release 생성(whl·exe 첨부 — 사용자 확인 후).
