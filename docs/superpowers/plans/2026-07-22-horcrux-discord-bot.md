# Horcrux 디스코드 봇 프론트엔드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 랩서버 상주 디스코드 봇 — 채널 메시지로 log/ask, 슬래시 커맨드로 feedback/absorb/seed.

**Architecture:** 단일 프로세스. 신규 모듈 `src/horcrux/bot.py` 하나에 순수 대화 로직(테스트 대상)과 discord.py 글루를 분리해 담는다. 코어 함수는 기존 시그니처 그대로 재사용, 백엔드 변경은 `run_feedback` 반환값 1건.

**Tech Stack:** Python 3.10+, discord.py ≥2.6, pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-horcrux-discord-bot-design.md`

## Global Constraints

- pytest 실행은 반드시 `python -m pytest -q --basetemp=.pytest_tmp` (샌드박스 temp 권한 문제).
- 테스트에서 LLM·디스코드 네트워크 호출 금지 — 전부 모킹.
- 봇 토큰은 `HORCRUX_DISCORD_TOKEN` 환경변수로만. 코드·레포·테스트에 실제 토큰 금지.
- 채널 이름 기본값: log=`실험로그`, ask=`질문` (env `HORCRUX_LOG_CHANNEL`/`HORCRUX_ASK_CHANNEL` 오버라이드).
- 재질문 최대 3회, 응답 대기 타임아웃 600초, 디스코드 메시지 2000자 제한.
- 커밋 메시지는 기존 스타일: `feat:`/`fix:`/`docs:` + 한국어 요약.
- 구현은 워크트리에서 (superpowers:using-git-worktrees — 예: `bot-impl` 브랜치).

---

### Task 1: 백엔드 변경 2건 — `run_feedback` 반환값 + `save_unparsed` 추출

**Files:**
- Modify: `src/horcrux/feedback.py`
- Modify: `src/horcrux/ingest.py` (파싱 실패 needs_review 폴백을 함수로 추출 — CLI·봇 공용, 중복 제거)
- Modify: `src/horcrux/cli.py:50` (feedback 분기)
- Test: `tests/test_feedback.py`, `tests/test_ingest.py`

**Interfaces:**
- Produces: `run_feedback(cfg, record_id, resolved, cause, note) -> str` — 결과 메시지 반환 (봇·CLI 공용).
- Produces: `ingest.save_unparsed(vault, text, err) -> Path` — 파싱 실패 원문을 needs_review로 저장.

- [ ] **Step 1: 기존 테스트를 반환값 검증으로 수정 (실패 확인용)**

`tests/test_feedback.py` 전체를 다음으로 교체:

```python
from horcrux import feedback as fb
from horcrux.config import Config
from horcrux.records import ExperimentRecord, SuspectedCause, load_record, record_path, save_record


def test_run_feedback_updates(tmp_path):
    rec = ExperimentRecord(id="2026-07-19_x-001", date="2026-07-19",
                           suspected_causes=[SuspectedCause(cause="타겟 산화")])
    save_record(tmp_path, rec, "원문", "정리")
    msg = fb.run_feedback(Config(vault=tmp_path), rec.id, True, "타겟 산화", "연마 후 해결")
    assert "해결로 기록됨" in msg and "타겟 산화" in msg
    loaded, _ = load_record(record_path(tmp_path, rec.id))
    assert loaded.resolution.resolved is True
    assert loaded.resolution.actual_cause == "타겟 산화"
    assert loaded.suspected_causes[0].status == "confirmed"


def test_run_feedback_missing_record(tmp_path):
    msg = fb.run_feedback(Config(vault=tmp_path), "없는-id", True, None, "")
    assert "찾을 수 없음" in msg
```

`tests/test_ingest.py` 끝에 추가 (파일 상단 임포트에 `load_record`는 이미 있음):

```python
def test_save_unparsed_preserves_text(tmp_path):
    path = ingest.save_unparsed(tmp_path, "원문 로그", "boom")
    rec, body = load_record(path)
    assert rec.needs_review is True
    assert "원문 로그" in body
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_feedback.py tests/test_ingest.py`
Expected: FAIL — `run_feedback`이 `None` 반환이라 TypeError, `save_unparsed`는 AttributeError.

- [ ] **Step 3: 구현**

`src/horcrux/feedback.py`의 `run_feedback`을 다음으로 교체:

```python
def run_feedback(cfg: Config, record_id: str, resolved: bool, cause: str | None, note: str) -> str:
    if not record_path(cfg.vault, record_id).exists():
        return f"레코드를 찾을 수 없음: {record_id}"
    rec = update_resolution(cfg.vault, record_id, resolved, cause, note)
    state = "해결" if resolved else "미해결"
    return f"{rec.id}: {state}로 기록됨" + (f" (원인: {cause})" if cause else "")
```

`src/horcrux/cli.py`의 feedback 분기를 print 감싸기로 수정:

```python
    elif args.cmd == "feedback":
        from .feedback import run_feedback
        print(run_feedback(cfg, args.record_id, args.resolved == "y", args.cause, args.note))
```

`src/horcrux/ingest.py`에 함수 추가 (`run_log` 위 — 필요한 이름들은 이미 임포트돼 있음):

```python
def save_unparsed(vault: Path, text: str, err: str) -> Path:
    """파싱 실패 원문을 needs_review로 보존 — CLI·봇 공용 (데이터 유실 방지)."""
    today = _date.today().isoformat()
    rec = ExperimentRecord(id=make_record_id(vault, today, "exp"), date=today, needs_review=True)
    return save_record(vault, rec, text, f"(자동 파싱 실패: {err})")
```

`run_log`의 except 블록을 이 함수 사용으로 교체:

```python
    except Exception as e:
        path = save_unparsed(cfg.vault, text, str(e))
        print(f"파싱에 실패해 원문만 저장했습니다 (needs_review): {path}")
        return path
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_feedback.py tests/test_ingest.py tests/test_cli.py`
Expected: PASS 전부.

- [ ] **Step 5: Commit**

```bash
git add src/horcrux/feedback.py src/horcrux/ingest.py src/horcrux/cli.py tests/test_feedback.py tests/test_ingest.py
git commit -m "feat: run_feedback 메시지 반환·save_unparsed 추출 (봇 공용 준비)"
```

---

### Task 2: bot.py 순수 대화 로직 (세션 상태 머신 + 메시지 분할)

**Files:**
- Modify: `pyproject.toml` (dependencies에 discord.py 추가)
- Create: `src/horcrux/bot.py`
- Create: `tests/test_bot.py`

**Interfaces:**
- Consumes: `ingest.parse_log(cfg, text, vcfg) -> ParsedLog`, `ingest.missing_required(parsed, vcfg) -> list[str]`, `ingest.to_record(vault, parsed, date) -> ExperimentRecord`, `ingest.save_unparsed(vault, text, err) -> Path` (Task 1), `records.save_record(vault, rec, text, summary) -> Path`, `absorb.run_absorb(cfg) -> int`
- Produces: `LogSession` (dataclass: `text: str`, `parsed: ParsedLog`, `rounds: int = 0`, `files: list[tuple[str, bytes]]`), `advance_log(cfg, vcfg, session: LogSession | None, text: str, files: list[tuple[str, bytes]] | None = None) -> tuple[LogSession | None, list[str]]`, `finalize_log(cfg, vcfg, session: LogSession) -> list[str]` (저장·첨부만 — absorb 없음), `absorb_after(cfg) -> list[str]` (0건이면 빈 리스트), `save_attachments(vault, rec_id, files) -> list[str]` (옵시디언 링크 목록), `split_message(text: str, limit: int = 2000) -> list[str]`, `route(channel_name: str | None, log_channel: str, ask_channel: str) -> str | None` (`"log"`/`"ask"`/`None`)

- [ ] **Step 1: 의존성 추가 + 설치**

`pyproject.toml`의 `dependencies` 배열에 `"discord.py>=2.6"` 추가 (기존 pydantic·pyyaml 줄 옆).

Run: `pip install -e .`
Expected: discord.py 2.6 이상 설치 (현재 최신 2.7.x — 버전 문자열에 얽매이지 말 것). 확인: `python -c "import discord; print(discord.__version__)"`

- [ ] **Step 2: 실패 테스트 작성**

`tests/test_bot.py` 생성:

```python
import pytest

from horcrux import bot
from horcrux.bot import (
    LogSession, absorb_after, advance_log, finalize_log, route,
    save_attachments, split_message,
)
from horcrux.config import Config, VaultConfig
from horcrux.ingest import ParsedLog
from horcrux.records import Parameter, Symptom

VC = VaultConfig(
    required_fields=["objective", "parameters", "results", "symptom", "actions_taken"],
    required_parameters=[],
)


def full_parsed():
    return ParsedLog(
        experiment_type="박막 증착", objective="ITO 증착",
        parameters=[Parameter(name="RF power", value="150W")],
        results="증착률 5nm/min", summary="정리 서술",
        symptom=Symptom(category="none", description="문제 없음"),
    )


def cfg(tmp_path):
    return Config(vault=tmp_path, provider="claude")


def saved_files(tmp_path):
    d = tmp_path / "raw" / "experiments"
    return list(d.glob("*.md")) if d.exists() else []


# --- split_message ---

def test_split_message_short():
    assert split_message("짧은 답") == ["짧은 답"]


def test_split_message_long():
    chunks = split_message("가" * 4500)
    assert [len(c) for c in chunks] == [2000, 2000, 500]
    assert "".join(chunks) == "가" * 4500


def test_split_message_empty():
    assert split_message("") == []


# --- route (채널 매핑 분기) ---

def test_route_channel_mapping():
    assert route("실험로그", "실험로그", "질문") == "log"
    assert route("질문", "실험로그", "질문") == "ask"
    assert route("잡담", "실험로그", "질문") is None
    assert route(None, "실험로그", "질문") is None  # DM 등 이름 없는 채널


# --- advance_log / finalize_log ---

def test_advance_log_complete_saves(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "parse_log", lambda c, t, v: full_parsed())
    session, msgs = advance_log(cfg(tmp_path), VC, None, "완결 로그 원문")
    assert session is None
    assert "저장됨" in "\n".join(msgs)
    assert len(saved_files(tmp_path)) == 1


def test_advance_log_gaps_asks_question(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "parse_log", lambda c, t, v: ParsedLog())  # 전부 빈 필드
    session, msgs = advance_log(cfg(tmp_path), VC, None, "빈약한 로그")
    assert session is not None and session.rounds == 1
    assert "알려주세요" in msgs[0]
    assert saved_files(tmp_path) == []  # 아직 저장 안 됨


def test_advance_log_round_cap_saves_after_three(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "parse_log", lambda c, t, v: ParsedLog())  # 계속 빈 필드
    session, _ = advance_log(cfg(tmp_path), VC, None, "빈약한 로그")
    for expected_round in (2, 3):
        session, msgs = advance_log(cfg(tmp_path), VC, session, "여전히 빈약")
        assert session is not None and session.rounds == expected_round
    session, msgs = advance_log(cfg(tmp_path), VC, session, "마지막도 빈약")  # 4번째 → 저장
    assert session is None
    joined = "\n".join(msgs)
    assert "저장됨" in joined and "일부 필수 정보" in joined
    assert len(saved_files(tmp_path)) == 1


def test_advance_log_empty_reply_skips_reparse(monkeypatch, tmp_path):
    calls = []

    def fake(c, t, v):
        calls.append(t)
        return ParsedLog()

    monkeypatch.setattr(bot, "parse_log", fake)
    session, _ = advance_log(cfg(tmp_path), VC, None, "빈약한 로그")
    session, msgs = advance_log(cfg(tmp_path), VC, session, "   ")  # 빈 답변 (첨부만 등)
    assert session is None
    assert len(calls) == 1  # 재파싱 없이 있는 정보로 저장
    assert "저장됨" in "\n".join(msgs)
    assert len(saved_files(tmp_path)) == 1


def test_advance_log_parse_failure_saves_needs_review(monkeypatch, tmp_path):
    def boom(c, t, v):
        raise RuntimeError("CLI 실패")
    monkeypatch.setattr(bot, "parse_log", boom)
    session, msgs = advance_log(cfg(tmp_path), VC, None, "원문")
    assert session is None
    assert "needs_review" in msgs[0]
    assert len(saved_files(tmp_path)) == 1


def test_advance_log_continue_parse_failure_finalizes_previous(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "parse_log", lambda c, t, v: ParsedLog())
    session, _ = advance_log(cfg(tmp_path), VC, None, "빈약한 로그")

    def boom(c, t, v):
        raise RuntimeError("재파싱 실패")
    monkeypatch.setattr(bot, "parse_log", boom)
    session, msgs = advance_log(cfg(tmp_path), VC, session, "추가 답변")
    assert session is None
    assert "저장됨" in "\n".join(msgs)  # 직전 파싱 결과로 저장 진행
    assert len(saved_files(tmp_path)) == 1


def test_finalize_log_saves_with_attachments(tmp_path):
    session = LogSession(text="원문", parsed=full_parsed(), files=[("결과.png", b"PNG")])
    msgs = finalize_log(cfg(tmp_path), VC, session)
    assert "저장됨" in msgs[0]
    md = saved_files(tmp_path)[0]
    att = tmp_path / "raw" / "attachments" / md.stem / "결과.png"
    assert att.read_bytes() == b"PNG"
    assert "![[" in md.read_text(encoding="utf-8")  # 본문에 옵시디언 임베드 링크


# --- save_attachments / absorb_after ---

def test_save_attachments_writes_and_links(tmp_path):
    links = save_attachments(tmp_path, "rid-001", [("a.png", b"1")])
    assert (tmp_path / "raw" / "attachments" / "rid-001" / "a.png").read_bytes() == b"1"
    assert links == ["![[raw/attachments/rid-001/a.png]]"]


def test_save_attachments_sanitizes_filename(tmp_path):
    save_attachments(tmp_path, "rid-001", [("..\\evil.txt", b"x"), ("..", b"y")])
    d = tmp_path / "raw" / "attachments" / "rid-001"
    assert (d / "evil.txt").read_bytes() == b"x"
    assert (d / "attachment").read_bytes() == b"y"  # '.'/'..'는 안전한 이름으로 대체


def test_save_attachments_empty(tmp_path):
    assert save_attachments(tmp_path, "rid", []) == []


def test_advance_log_parse_failure_keeps_attachments(monkeypatch, tmp_path):
    def boom(c, t, v):
        raise RuntimeError("CLI 실패")
    monkeypatch.setattr(bot, "parse_log", boom)
    session, msgs = advance_log(cfg(tmp_path), VC, None, "원문", files=[("img.png", b"P")])
    assert session is None and "needs_review" in msgs[0]
    rec_id = saved_files(tmp_path)[0].stem
    assert (tmp_path / "raw" / "attachments" / rec_id / "img.png").read_bytes() == b"P"


def test_absorb_after_reports_count(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "run_absorb", lambda c: 2)
    assert absorb_after(cfg(tmp_path)) == ["위키 갱신: 2건"]


def test_absorb_after_zero_is_silent(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "run_absorb", lambda c: 0)
    assert absorb_after(cfg(tmp_path)) == []


def test_absorb_after_failure_warns(monkeypatch, tmp_path):
    def boom(c):
        raise RuntimeError("편찬 실패")
    monkeypatch.setattr(bot, "run_absorb", boom)
    assert "위키 편찬 실패" in absorb_after(cfg(tmp_path))[0]
```

- [ ] **Step 3: 실패 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_bot.py`
Expected: FAIL — 수집 단계 임포트 에러 `ImportError: cannot import name 'bot' from 'horcrux'` (from-임포트라 ModuleNotFoundError가 아님)

- [ ] **Step 4: 구현 — bot.py 순수 로직 부분**

`src/horcrux/bot.py` 생성 (이 태스크에서는 순수 로직까지만 — 글루는 Task 3):

```python
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path

from .absorb import run_absorb
from .config import Config, VaultConfig
from .ingest import ParsedLog, missing_required, parse_log, save_unparsed, to_record
from .records import save_record

MAX_ROUNDS = 3       # 재질문 최대 횟수
REPLY_TIMEOUT = 600  # 재질문 응답 대기 (초)
MSG_LIMIT = 2000     # 디스코드 메시지 길이 제한

# ponytail: 전역 볼트 쓰기 락 — 동시 저장 시 record id 순번 경쟁(덮어쓰기)·
# _absorb_log.json 경쟁 방지. 처리량이 문제되면 볼트별 락으로 세분화.
_VAULT_LOCK = threading.Lock()


def _locked(fn, *args):
    """볼트 쓰기 진입점 공용 래퍼 — 슬래시 커맨드(run_absorb/run_seed/run_feedback)도
    반드시 이 경유로 호출해 락을 우회하지 않게 한다."""
    with _VAULT_LOCK:
        return fn(*args)


@dataclass
class LogSession:
    text: str          # 누적 원문 (원본 + 추가 답변)
    parsed: ParsedLog
    rounds: int = 0    # 지금까지 던진 재질문 횟수
    files: list[tuple[str, bytes]] = field(default_factory=list)  # 첨부 (파일명, 내용)


def split_message(text: str, limit: int = MSG_LIMIT) -> list[str]:
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def route(channel_name: str | None, log_channel: str, ask_channel: str) -> str | None:
    """채널 이름 → 처리 종류. 매핑 밖 채널·DM은 None (무시)."""
    if channel_name == log_channel:
        return "log"
    if channel_name == ask_channel:
        return "ask"
    return None


def save_attachments(vault: Path, rec_id: str, files: list[tuple[str, bytes]]) -> list[str]:
    """첨부를 볼트에 저장하고 옵시디언 임베드 링크 목록 반환. 내용 분석은 없음(보관만)."""
    if not files:
        return []
    d = Path(vault) / "raw" / "attachments" / rec_id
    d.mkdir(parents=True, exist_ok=True)
    links = []
    for name, data in files:
        safe = os.path.basename(name.replace("\\", "/"))
        if safe in ("", ".", ".."):  # '..'가 통과하면 디렉터리 자체가 타겟 — 저장 실패로 레코드 유실
            safe = "attachment"
        (d / safe).write_bytes(data)
        links.append(f"![[raw/attachments/{rec_id}/{safe}]]")
    return links


def advance_log(cfg: Config, vcfg: VaultConfig, session: LogSession | None, text: str,
                files: list[tuple[str, bytes]] | None = None,
                ) -> tuple[LogSession | None, list[str]]:
    """log 대화 한 스텝. (다음 세션 또는 None, 회신 메시지들) 반환."""
    files = files or []
    if session is None:
        try:
            parsed = parse_log(cfg, text, vcfg)
        except Exception as e:
            with _VAULT_LOCK:
                path = save_unparsed(cfg.vault, text, str(e))
                save_attachments(cfg.vault, path.stem, files)  # 첨부도 유실 없이 보존
            return None, [f"파싱에 실패해 원문만 저장했습니다 (needs_review): {path}"]
        session = LogSession(text=text, parsed=parsed, files=list(files))
    else:
        session.files.extend(files)
        if not text.strip():  # 빈 답변(첨부만 등) — 재파싱 없이 있는 정보로 저장
            return None, finalize_log(cfg, vcfg, session)
        session.text = f"{session.text}\n\n[추가 답변]\n{text}"
        try:
            session.parsed = parse_log(cfg, session.text, vcfg)
        except Exception:
            return None, finalize_log(cfg, vcfg, session)  # 직전 파싱 결과로 저장 진행
    gaps = missing_required(session.parsed, vcfg)
    if gaps and session.rounds < MAX_ROUNDS:
        session.rounds += 1
        qs = "\n".join(f"- {q}" for q in gaps)
        return session, [f"기록 품질을 위해 추가로 알려주세요 (10분 무응답 시 그대로 저장):\n{qs}"]
    return None, finalize_log(cfg, vcfg, session)


def finalize_log(cfg: Config, vcfg: VaultConfig, session: LogSession) -> list[str]:
    """저장 + 첨부만 — 위키 편찬은 absorb_after로 분리 (저장 확인을 즉시 회신하기 위함)."""
    today = _date.today().isoformat()
    with _VAULT_LOCK:
        rec = to_record(cfg.vault, session.parsed, today)
        links = save_attachments(cfg.vault, rec.id, session.files)
        body = session.text + ("\n\n[첨부]\n" + "\n".join(links) if links else "")
        path = save_record(cfg.vault, rec, body, session.parsed.summary)
    msgs = [f"저장됨: `{rec.id}` ({path})\n{session.parsed.summary}".strip()]
    if missing_required(session.parsed, vcfg):
        msgs.append("(일부 필수 정보가 비어 있는 채로 저장됨)")
    return msgs


def absorb_after(cfg: Config) -> list[str]:
    """저장 확인과 분리된 후속 위키 편찬. 갱신 0건이면 조용히 빈 리스트."""
    try:
        with _VAULT_LOCK:
            n = run_absorb(cfg)
        return [f"위키 갱신: {n}건"] if n else []
    except Exception as e:
        return [f"(위키 편찬 실패 — /absorb로 재시도: {e})"]
```

- [ ] **Step 5: 통과 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_bot.py`
Expected: PASS 전부 (18개).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/horcrux/bot.py tests/test_bot.py
git commit -m "feat: 봇 순수 대화 로직 — log 세션 상태 머신·메시지 분할"
```

---

### Task 3: 디스코드 글루 — HorcruxBot 클라이언트 + 슬래시 커맨드

**Files:**
- Modify: `src/horcrux/bot.py` (글루 추가)
- Test: `tests/test_bot.py` (오프라인 구성 테스트 추가)

**Interfaces:**
- Consumes: Task 2의 `advance_log`/`finalize_log`/`absorb_after`/`route`/`split_message`, `diagnose.diagnose(cfg, text) -> str`, `feedback.run_feedback(...) -> str` (Task 1), `seed.run_seed(cfg, n) -> int`
- Produces: `build_client(cfg: Config) -> HorcruxBot` (연결 없이 구성 가능 — 테스트 대상), `run_bot(cfg: Config) -> None` (토큰 검사 후 `client.run(token)`)

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_bot.py` 끝에 추가:

```python
# --- 디스코드 글루 (오프라인 구성 검증) ---

def test_build_client_registers_commands(tmp_path):
    c = bot.build_client(cfg(tmp_path))
    assert {cmd.name for cmd in c.tree.get_commands()} == {"feedback", "absorb", "seed"}
    assert c.intents.message_content is True


def test_run_bot_without_token_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("HORCRUX_DISCORD_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="HORCRUX_DISCORD_TOKEN"):
        bot.run_bot(cfg(tmp_path))
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_bot.py`
Expected: 신규 2개 FAIL — `AttributeError: module 'horcrux.bot' has no attribute 'build_client'`

- [ ] **Step 3: 구현 — 글루 추가**

`src/horcrux/bot.py` 상단 임포트에 추가 (Task 2에서 만든 임포트 아래):

```python
import asyncio
import os

import discord
from discord import app_commands

from .config import load_vault_config   # 기존 .config 임포트 줄에 이름만 추가해도 됨
from .diagnose import diagnose
from .feedback import run_feedback
from .seed import run_seed
```

파일 끝에 글루 추가:

```python
class HorcruxBot(discord.Client):
    def __init__(self, cfg: Config, **kwargs):
        super().__init__(**kwargs)
        self.cfg = cfg
        self.log_channel = os.environ.get("HORCRUX_LOG_CHANNEL", "실험로그")
        self.ask_channel = os.environ.get("HORCRUX_ASK_CHANNEL", "질문")
        # (channel_id, user_id) → "processing"(LLM 처리 중) | "waiting"(재질문 답변 대기)
        self.busy: dict[tuple[int, int], str] = {}
        self._claimed: set[int] = set()  # wait_for가 소비할 메시지 id — on_message 오탐 방지
        self._synced = False
        self.tree = app_commands.CommandTree(self)
        _register_commands(self)

    async def on_ready(self):
        # 개발 중엔 guild-scoped sync가 즉시 반영 (글로벌은 전파 지연).
        # on_ready는 재연결마다 다시 불림 — sync 반복은 rate limit 위험이라 1회 가드.
        if not self._synced:
            for g in self.guilds:
                self.tree.copy_global_to(guild=g)
                await self.tree.sync(guild=g)
            self._synced = True
        print(f"봇 로그인: {self.user} / 채널 매핑: #{self.log_channel}(log) #{self.ask_channel}(ask)")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.id in self._claimed:
            # wait_for가 소비한 재질문 답변 — dispatch가 wait_for future를 먼저 깨우므로
            # (Python 3.12+에선 _log_flow가 먼저 재개됨) busy 상태만으론 오탐이 남
            self._claimed.discard(message.id)
            return
        key = (message.channel.id, message.author.id)
        state = self.busy.get(key)
        if state == "waiting":
            return  # 대기 중 경합 백스톱
        if state == "processing":
            # LLM 처리 중엔 대기 리스너가 없음 — 무통보 유실 대신 안내
            await self._reply(message, "⏳ 이전 메시지 처리 중 — 끝나면 다시 보내주세요.")
            return
        kind = route(getattr(message.channel, "name", None), self.log_channel, self.ask_channel)
        if kind == "log":
            await self._log_flow(message)
        elif kind == "ask":
            await self._ask_flow(message)

    @staticmethod
    async def _reply(message: discord.Message, text: str) -> None:
        # 원 메시지가 삭제됐으면 reply가 400 (Unknown message) — 채널 전송으로 폴백
        try:
            await message.reply(text)
        except discord.HTTPException:
            await message.channel.send(text)

    async def _send(self, message: discord.Message, msgs: list[str]) -> None:
        # 첫 청크는 원 메시지에 답장(reply) — 다중 유저 채널 귀속 명확 + 작성자 알림
        first = True
        for m in msgs:
            for chunk in split_message(m):
                if first:
                    await self._reply(message, chunk)
                    first = False
                else:
                    await message.channel.send(chunk)

    @staticmethod
    async def _read_files(message: discord.Message) -> list[tuple[str, bytes]]:
        return [(a.filename, await a.read()) for a in message.attachments]

    async def _log_flow(self, message: discord.Message) -> None:
        key = (message.channel.id, message.author.id)
        self.busy[key] = "processing"
        try:
            if not message.content.strip():
                await self._reply(message, "첨부만으론 기록할 수 없어요 — 텍스트 로그와 함께 보내주세요.")
                return
            # LLM 완료까지 진행률 신호가 없으므로 접수 확인이 유일한 체감 장치
            await self._reply(message, "🔬 로그 분석 중... (수십 초~수 분 걸릴 수 있어요)")
            vcfg = load_vault_config(self.cfg.vault)
            files = await self._read_files(message)
            async with message.channel.typing():
                session, msgs = await asyncio.to_thread(
                    advance_log, self.cfg, vcfg, None, message.content, files)
            await self._send(message, msgs)
            while session:
                def check(m, _a=message.author, _c=message.channel):
                    ok = m.author == _a and m.channel == _c
                    if ok:
                        self._claimed.add(m.id)  # dispatch 시점(동기)에 선점 — on_message 오탐 방지
                    return ok
                self.busy[key] = "waiting"
                try:
                    reply = await self.wait_for("message", check=check, timeout=REPLY_TIMEOUT)
                    self.busy[key] = "processing"
                    await self._reply(reply, "🔬 답변 반영 중...")
                    rfiles = await self._read_files(reply)
                    async with message.channel.typing():
                        session, msgs = await asyncio.to_thread(
                            advance_log, self.cfg, vcfg, session, reply.content, rfiles)
                except asyncio.TimeoutError:
                    self.busy[key] = "processing"
                    await self._reply(message, "⏱ 응답이 없어 있는 정보로 저장합니다...")
                    session, msgs = None, await asyncio.to_thread(
                        finalize_log, self.cfg, vcfg, session)
                await self._send(message, msgs)
            # 저장 확인과 분리된 후속 위키 편찬 (0건이면 조용히 생략)
            wiki_msgs = await asyncio.to_thread(absorb_after, self.cfg)
            await self._send(message, wiki_msgs)
        except Exception as e:
            await self._send(message, [f"⚠ 오류: {e}"])
        finally:
            self.busy.pop(key, None)

    async def _ask_flow(self, message: discord.Message) -> None:
        key = (message.channel.id, message.author.id)
        self.busy[key] = "processing"
        try:
            if message.attachments:
                await self._reply(message, "(첨부는 진단 분석에 사용되지 않아요 — 텍스트만 참고합니다)")
            if not message.content.strip():
                return
            await self._reply(message, "🔍 과거 기록 검색·진단 중... (수십 초~수 분 걸릴 수 있어요)")
            async with message.channel.typing():
                answer = await asyncio.to_thread(diagnose, self.cfg, message.content)
            await self._send(message, [answer.strip() or "(빈 응답)"])
        except Exception as e:
            await self._send(message, [f"⚠ 오류: {e}"])
        finally:
            self.busy.pop(key, None)


async def _followup(interaction: discord.Interaction, msg: str) -> None:
    try:
        for chunk in split_message(msg):  # 긴 예외 문자열 등 2000자 초과 대비
            await interaction.followup.send(chunk)
    except discord.HTTPException:
        # ponytail: defer 토큰 15분 만료(장시간 /seed·/absorb) 대비 — 채널 전송 폴백
        for chunk in split_message(msg):
            await interaction.channel.send(chunk)


def _register_commands(bot_: HorcruxBot) -> None:
    @bot_.tree.command(name="feedback", description="레코드 해결 여부·실제 원인 기록")
    @app_commands.describe(record_id="레코드 id", resolved="해결 여부",
                           cause="확인된 실제 원인", note="메모")
    async def feedback_cmd(interaction: discord.Interaction, record_id: str,
                           resolved: bool, cause: str | None = None, note: str = ""):
        await interaction.response.defer()
        try:
            msg = await asyncio.to_thread(_locked, run_feedback, bot_.cfg, record_id, resolved, cause, note)
        except Exception as e:
            msg = f"⚠ 오류: {e}"
        await _followup(interaction, msg)

    @bot_.tree.command(name="absorb", description="위키 아티클 편찬 (재시도·수동 실행)")
    async def absorb_cmd(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            n = await asyncio.to_thread(_locked, run_absorb, bot_.cfg)  # 락 우회 금지
            msg = f"아티클 갱신: {n}건"
        except Exception as e:
            msg = f"⚠ 오류: {e}"
        await _followup(interaction, msg)

    @bot_.tree.command(name="seed", description="합성 데모 데이터 생성")
    @app_commands.describe(n="생성 건수")
    async def seed_cmd(interaction: discord.Interaction, n: int = 6):
        await interaction.response.defer()
        try:
            saved = await asyncio.to_thread(_locked, run_seed, bot_.cfg, n)  # 락 우회 금지
            msg = f"합성 로그 {saved}건 저장 (위키 편찬 포함)"
        except Exception as e:
            msg = f"⚠ 오류: {e}"
        await _followup(interaction, msg)


def build_client(cfg: Config) -> HorcruxBot:
    intents = discord.Intents.default()
    intents.message_content = True  # privileged — 개발자 포털에서도 켜야 함
    return HorcruxBot(cfg, intents=intents)


def run_bot(cfg: Config) -> None:
    token = os.environ.get("HORCRUX_DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "HORCRUX_DISCORD_TOKEN 미설정 — Discord 개발자 포털에서 봇 토큰을 발급해 환경변수로 넣어주세요")
    build_client(cfg).run(token)
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_bot.py`
Expected: PASS 전부 (20개).

- [ ] **Step 5: Commit**

```bash
git add src/horcrux/bot.py tests/test_bot.py
git commit -m "feat: 디스코드 글루 — 채널 매핑 log/ask 흐름·슬래시 커맨드 3종"
```

---

### Task 4: CLI `horcrux bot` 서브커맨드

**Files:**
- Modify: `src/horcrux/cli.py`
- Test: `tests/test_cli.py` (기존 파일 끝에 추가)

**Interfaces:**
- Consumes: `bot.run_bot(cfg)` (Task 3)

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_cli.py` 끝에 추가:

```python
def test_cli_bot_dispatch(monkeypatch):
    called = {}
    import horcrux.bot as bot_mod
    monkeypatch.setattr(bot_mod, "run_bot", lambda cfg: called.setdefault("cfg", cfg))
    from horcrux.cli import main
    main(["bot"])
    assert "cfg" in called
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_cli.py`
Expected: 신규 1개 FAIL — `bot` 서브커맨드 없어 argparse가 SystemExit(2).

- [ ] **Step 3: 구현**

`src/horcrux/cli.py`에 서브파서 추가 (seed 파서 아래):

```python
    sub.add_parser("bot", help="디스코드 봇 실행")
```

분기 추가 (seed 분기 아래):

```python
    elif args.cmd == "bot":
        from . import bot
        bot.run_bot(cfg)
```

주의: `from .bot import run_bot`이 아니라 `from . import bot` 후 `bot.run_bot(cfg)` — 테스트의 monkeypatch가 모듈 속성을 바꾸므로 모듈 경유 호출이어야 반영된다.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_cli.py`
Expected: PASS 전부.

- [ ] **Step 5: Commit**

```bash
git add src/horcrux/cli.py tests/test_cli.py
git commit -m "feat: horcrux bot 서브커맨드"
```

---

### Task 5: 문서 — AGENTS.md 레이어 경계 + README 봇 섹션

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`

- [ ] **Step 1: AGENTS.md에 경계 섹션 추가**

`AGENTS.md` 끝에 추가:

```markdown
## 레이어 소유 경계 (병렬 작업 시)

| 영역 | 소유 파일 |
|---|---|
| 프론트 (디스코드 봇) | `src/horcrux/bot.py`, `tests/test_bot.py` |
| 백엔드 (코어) | `src/horcrux/{ingest,diagnose,retrieval,absorb,feedback,records,llm,config,seed}.py` + 기존 테스트 |
| 공용 접점 | `cli.py`, `pyproject.toml`, `README.md`, `docs/**` |

프론트가 의존하는 백엔드 인터페이스(전체 목록):
`parse_log(cfg, text, vcfg)` · `missing_required(parsed, vcfg)` · `to_record(vault, parsed, date)` ·
`save_record(vault, rec, text, summary)` · `save_unparsed(vault, text, err)` · `load_vault_config(vault)` ·
`diagnose(cfg, text)` · `run_absorb(cfg)` · `run_feedback(cfg, id, resolved, cause, note) -> str` ·
`run_seed(cfg, n)`.
시그니처 변경은 백엔드 먼저 수정 후 프론트가 따라간다 — 같은 파일 동시 수정 금지.
```

- [ ] **Step 2: README에 봇 섹션 추가**

`README.md` 설치 섹션 아래에 추가:

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md README.md
git commit -m "docs: 봇 설정·실행 가이드 + 레이어 소유 경계"
```

---

### Task 6: 전체 검증 + 수동 스모크

**Files:** 없음 (검증만)

- [ ] **Step 1: 전체 테스트**

Run: `python -m pytest -q --basetemp=.pytest_tmp`
Expected: 전부 PASS (기존 61 + 신규 ≈22).

- [ ] **Step 2: 수동 스모크 (사용자 개입 필요 — 토큰·서버 준비는 README 절차)**

1. `$env:HORCRUX_DISCORD_TOKEN="<토큰>"; horcrux bot` — "봇 로그인" 출력 확인
2. `#실험로그`에 일부러 빈약한 로그 입력 → "🔬 로그 분석 중" 접수(원 메시지에 답장 형태) → 재질문 → 답변 → **"저장됨"(경로 포함) 즉시 회신 → 잠시 후 "위키 갱신: n건" 후속 메시지** 확인
3. 사진 첨부한 로그 입력 → 저장 후 볼트 `raw/attachments/<id>/`에 파일 + md 본문 `![[...]]` 링크 확인
4. LLM 처리 중 같은 채널에 연속 메시지 → "⏳ 이전 메시지 처리 중" 안내 확인
5. 매핑 밖 채널(예: #잡담)에 메시지 → 봇 무반응 확인
6. `#질문`에 문제 입력 → "🔍 검색·진단 중" 접수 → 사례 인용 답변 확인
7. `/feedback record_id:<위 id> resolved:True cause:테스트` → "해결로 기록됨" 확인

- [ ] **Step 3: 브랜치 마무리**

superpowers:finishing-a-development-branch 스킬로 main 병합·정리.
