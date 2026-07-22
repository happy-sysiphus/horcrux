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


# --- 디스코드 글루 (오프라인 구성 검증) ---

def test_build_client_registers_commands(tmp_path):
    c = bot.build_client(cfg(tmp_path))
    assert {cmd.name for cmd in c.tree.get_commands()} == {"feedback", "absorb", "seed"}
    assert c.intents.message_content is True


def test_run_bot_without_token_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("HORCRUX_DISCORD_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="HORCRUX_DISCORD_TOKEN"):
        bot.run_bot(cfg(tmp_path))
