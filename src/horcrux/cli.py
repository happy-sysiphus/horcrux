from __future__ import annotations

import argparse
import sys

from .config import load_config
from .ingest import run_log


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
    args = p.parse_args(argv)
    cfg = load_config()

    if args.cmd == "log":
        run_log(cfg)
    elif args.cmd == "ask":
        from .diagnose import run_ask
        run_ask(cfg)
    elif args.cmd == "feedback":
        from .feedback import run_feedback
        run_feedback(cfg, args.record_id, args.resolved == "y", args.cause, args.note)
    elif args.cmd == "absorb":
        from .absorb import run_absorb
        n = run_absorb(cfg)
        print(f"아티클 갱신: {n}건")
    elif args.cmd == "seed":
        from .seed import run_seed
        run_seed(cfg, args.n)


if __name__ == "__main__":
    main()
