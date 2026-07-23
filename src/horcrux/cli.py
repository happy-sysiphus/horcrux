from __future__ import annotations

import argparse
import sys

from .config import load_config
from .ingest import run_log


def run_init() -> None:
    from .config import load_config, save_config
    cur = load_config()  # 기존 파일+env 반영값을 기본값으로 보여줌
    print("Horcrux 설정 — 빈 입력은 [현재값] 유지")

    def ask(label: str, cur_val) -> str:
        raw = input(f"{label} [{cur_val or ''}]: ").strip()
        return raw or (str(cur_val) if cur_val else "")

    token = ask("디스코드 봇 토큰", cur.discord_token)
    vault = ask("볼트 절대경로", cur.vault.as_posix())
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


def _utf8_console():
    for stream in (sys.stdout, sys.stdin, sys.stderr):
        try:
            if stream.encoding and stream.encoding.lower() != "utf-8":
                stream.reconfigure(encoding="utf-8")
        except Exception:
            pass  # 콘솔 인코딩 조정 실패는 치명적이지 않음


def main(argv: list[str] | None = None) -> None:
    _utf8_console()
    p = argparse.ArgumentParser(prog="horcrux", description="연구실 실험 기록·문제 진단 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("log", help="실험 로그 기록")
    sub.add_parser("ask", help="문제 질의")
    sub.add_parser("absorb", help="위키 아티클 편찬")
    fb = sub.add_parser("feedback", help="해결 여부·실제 원인 기록")
    fb.add_argument("record_id")
    fb.add_argument("--resolved", choices=["y", "n"], required=True)
    fb.add_argument("--cause", default=None, help="확인된 실제 원인")
    fb.add_argument("--note", default="")
    sd = sub.add_parser("seed", help="합성 데모 데이터 생성")
    sd.add_argument("-n", type=int, default=6)
    sub.add_parser("bot", help="디스코드 봇 실행")
    sub.add_parser("init", help="설정 마법사 (~/.horcrux/config.yaml 생성)")
    args = p.parse_args(argv)
    if args.cmd == "init":
        run_init()  # cfg 로드 전 분기 — 깨진 설정파일도 init으로 복구 가능해야 함
        return
    cfg = load_config()

    if args.cmd == "log":
        path = run_log(cfg)
        if path:
            from .absorb import run_absorb
            try:
                n = run_absorb(cfg)
                print(f"위키 갱신: {n}건")
            except Exception as e:
                print(f"(위키 편찬 실패 — 'horcrux absorb'로 재시도: {e})")
    elif args.cmd == "ask":
        from .diagnose import run_ask
        run_ask(cfg)
    elif args.cmd == "feedback":
        from .feedback import run_feedback
        print(run_feedback(cfg, args.record_id, args.resolved == "y", args.cause, args.note))
    elif args.cmd == "absorb":
        from .absorb import run_absorb
        n = run_absorb(cfg)
        print(f"아티클 갱신: {n}건")
    elif args.cmd == "seed":
        from .seed import run_seed
        run_seed(cfg, args.n)
    elif args.cmd == "bot":
        from . import bot
        bot.run_bot(cfg)


if __name__ == "__main__":
    main()
