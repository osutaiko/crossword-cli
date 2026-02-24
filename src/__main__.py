from __future__ import annotations

import argparse

from .game import play


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Play a .puz crossword in the terminal")
    parser.add_argument("puz_file", help="Path to a .puz puzzle file")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    play(args.puz_file)


if __name__ == "__main__":
    main()
