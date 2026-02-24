from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Puzzle:
    title: str
    author: str
    copyright: str
    width: int
    height: int
    solution: str
    state: str
    clues: list[str]
    notes: str


def _decode_c_string(blob: bytes) -> str:
    return blob.decode("latin-1", errors="replace")


def load_puz(path: str | Path) -> Puzzle:
    data = Path(path).read_bytes()

    if b"ACROSS&DOWN" not in data[:0x40]:
        raise ValueError("Not a valid .puz file (missing ACROSS&DOWN signature).")

    width = data[0x2C]
    height = data[0x2D]
    clue_count = int.from_bytes(data[0x2E:0x30], "little")
    grid_size = width * height

    offset = 0x34
    solution = _decode_c_string(data[offset : offset + grid_size])
    state = _decode_c_string(data[offset + grid_size : offset + (2 * grid_size)])

    strings_blob = data[offset + (2 * grid_size) :]
    parts = strings_blob.split(b"\x00")

    if len(parts) < 3 + clue_count:
        raise ValueError("Invalid .puz file: insufficient string data.")

    title = _decode_c_string(parts[0])
    author = _decode_c_string(parts[1])
    copyright_text = _decode_c_string(parts[2])
    clues = [_decode_c_string(p) for p in parts[3 : 3 + clue_count]]
    notes = _decode_c_string(parts[3 + clue_count]) if len(parts) > 3 + clue_count else ""

    return Puzzle(
        title=title,
        author=author,
        copyright=copyright_text,
        width=width,
        height=height,
        solution=solution,
        state=state,
        clues=clues,
        notes=notes,
    )
