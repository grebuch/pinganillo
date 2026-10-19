"""Command-line entry point: ``escuchator`` or ``python -m escuchator``."""

from __future__ import annotations

import argparse

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="escuchator", description="Local-first live meeting copilot.")
    parser.add_argument("--version", action="version", version=f"escuchator {__version__}")
    parser.add_argument(
        "--demo", action="store_true", help="scripted meeting: no audio, no model, no account"
    )
    parser.add_argument("--lang", choices=["en", "es"], help="interface language (default: system)")
    parser.add_argument("--diagnose", action="store_true", help="run the audio + Whisper self-test and exit")
    parser.add_argument("--engine", choices=["wasapi", "soundcard"], help="capture engine for --diagnose")
    args = parser.parse_args(argv)

    if args.diagnose:
        from .diagnostics import run

        return run(args.engine)

    from .ui.app import run as run_ui

    return run_ui(demo=args.demo, language=args.lang)


if __name__ == "__main__":
    raise SystemExit(main())
