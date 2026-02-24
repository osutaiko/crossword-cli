from __future__ import annotations

import os
import select
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .puz import Puzzle, load_puz

if os.name != "nt":
    import termios
    import tty


@dataclass
class Entry:
    number: int
    direction: str  # A or D
    clue: str
    cells: list[int]
    answer: str

    @property
    def key(self) -> str:
        return f"{self.number}{self.direction}"


class CrosswordGame:
    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.entries = self._build_entries()
        self.user = self._initial_user_grid()

        self.entry_map = {e.key: e for e in self.entries}
        self.across_entries = [e for e in self.entries if e.direction == "A"]
        self.down_entries = [e for e in self.entries if e.direction == "D"]

        self.cell_to_entries: dict[int, dict[str, Entry]] = {}
        for entry in self.entries:
            for cell in entry.cells:
                mapping = self.cell_to_entries.setdefault(cell, {})
                mapping[entry.direction] = entry

        self.cursor = self._first_fillable_cell()
        self.direction = "A"
        self.selected = self._entry_for_cell(self.cursor, self.direction)
        if not self.selected:
            self.direction = "D"
            self.selected = self._entry_for_cell(self.cursor, self.direction)
        self.show_wrong_progress = False

    def _first_fillable_cell(self) -> int:
        for i, ch in enumerate(self.puzzle.solution):
            if ch != ".":
                return i
        return 0

    def _initial_user_grid(self) -> list[str]:
        out: list[str] = []
        for ch in self.puzzle.state:
            if ch == ".":
                out.append(".")
            elif ch in "- ":
                out.append(" ")
            else:
                out.append(ch.upper())
        return out

    def _build_entries(self) -> list[Entry]:
        w = self.puzzle.width
        h = self.puzzle.height
        grid = self.puzzle.solution

        def idx(r: int, c: int) -> int:
            return (r * w) + c

        number = 1
        clue_index = 0
        entries: list[Entry] = []

        for r in range(h):
            for c in range(w):
                i = idx(r, c)
                if grid[i] == ".":
                    continue
                across = c == 0 or grid[idx(r, c - 1)] == "."
                down = r == 0 or grid[idx(r - 1, c)] == "."
                if across or down:
                    n = number
                    number += 1
                    if across:
                        if clue_index >= len(self.puzzle.clues):
                            raise ValueError("Clue count mismatch in puzzle.")
                        cells: list[int] = []
                        cc = c
                        while cc < w and grid[idx(r, cc)] != ".":
                            cells.append(idx(r, cc))
                            cc += 1
                        answer = "".join(grid[cell] for cell in cells)
                        entries.append(
                            Entry(
                                number=n,
                                direction="A",
                                clue=self.puzzle.clues[clue_index],
                                cells=cells,
                                answer=answer,
                            )
                        )
                        clue_index += 1

                    if down:
                        if clue_index >= len(self.puzzle.clues):
                            raise ValueError("Clue count mismatch in puzzle.")
                        cells = []
                        rr = r
                        while rr < h and grid[idx(rr, c)] != ".":
                            cells.append(idx(rr, c))
                            rr += 1
                        answer = "".join(grid[cell] for cell in cells)
                        entries.append(
                            Entry(
                                number=n,
                                direction="D",
                                clue=self.puzzle.clues[clue_index],
                                cells=cells,
                                answer=answer,
                            )
                        )
                        clue_index += 1

        if clue_index != len(self.puzzle.clues):
            raise ValueError("Clue count mismatch in puzzle.")

        entries.sort(key=lambda e: (e.number, e.direction))
        return entries

    def _rc_to_idx(self, row: int, col: int) -> int:
        return (row * self.puzzle.width) + col

    def _idx_to_rc(self, idx: int) -> tuple[int, int]:
        return divmod(idx, self.puzzle.width)

    def _is_block(self, idx: int) -> bool:
        return self.puzzle.solution[idx] == "."

    def _entry_for_cell(self, cell: int, direction: str) -> Entry | None:
        return self.cell_to_entries.get(cell, {}).get(direction)

    def _sync_selected_to_cursor(self) -> None:
        entry = self._entry_for_cell(self.cursor, self.direction)
        if entry:
            self.selected = entry
            return

        other = "D" if self.direction == "A" else "A"
        fallback = self._entry_for_cell(self.cursor, other)
        if fallback:
            self.direction = other
            self.selected = fallback

    def _entry_has_blank(self, entry: Entry) -> bool:
        return any(self.user[cell] == " " for cell in entry.cells)

    def _select_entry(self, entry: Entry) -> None:
        self.selected = entry
        self.direction = entry.direction
        self.cursor = entry.cells[0]

    def switch_direction_at_cursor(self, direction: str) -> bool:
        entry = self._entry_for_cell(self.cursor, direction)
        if not entry:
            return False
        self.direction = direction
        self.selected = entry
        return True

    def toggle_wrong_progress(self) -> bool:
        self.show_wrong_progress = not self.show_wrong_progress
        return self.show_wrong_progress

    def _find_first_partially_unfilled(self, directions: list[str]) -> Entry | None:
        for direction in directions:
            pool = self.across_entries if direction == "A" else self.down_entries
            for entry in pool:
                if self._entry_has_blank(entry):
                    return entry
        return None

    def _jump_to_first_partially_unfilled_alternating(self) -> bool:
        other = "D" if self.direction == "A" else "A"
        target = self._find_first_partially_unfilled([other, self.direction])
        if not target:
            return False
        self._select_entry(target)
        return True

    def _jump_to_next_partially_unfilled_from_selected(self, step: int = 1) -> bool:
        self._sync_selected_to_cursor()
        if not self.selected:
            return False

        pool = self.across_entries if self.selected.direction == "A" else self.down_entries
        if not pool:
            return False

        try:
            start_idx = pool.index(self.selected)
        except ValueError:
            start_idx = 0

        for offset in range(1, len(pool) + 1):
            candidate = pool[(start_idx + (offset * step)) % len(pool)]
            if self._entry_has_blank(candidate):
                self._select_entry(candidate)
                return True

        other = "D" if self.selected.direction == "A" else "A"
        target = self._find_first_partially_unfilled([other, self.selected.direction])
        if target:
            self._select_entry(target)
            return True
        return False

    def _next_scan_position(
        self,
        row: int,
        col: int,
        d_row: int,
        d_col: int,
        offset: int,
    ) -> tuple[int, int, bool]:
        w = self.puzzle.width
        h = self.puzzle.height
        total = w * h

        if d_col != 0:
            rank = (row * w) + col
            if d_col > 0:
                raw = rank + offset
                wrapped = raw >= total
            else:
                raw = rank - offset
                wrapped = raw < 0
            new_rank = raw % total
            next_row, next_col = divmod(new_rank, w)
            return next_row, next_col, wrapped

        rank = (col * h) + row
        if d_row > 0:
            raw = rank + offset
            wrapped = raw >= total
        else:
            raw = rank - offset
            wrapped = raw < 0
        new_rank = raw % total
        next_col = new_rank // h
        next_row = new_rank % h
        return next_row, next_col, wrapped

    def move_cursor(self, d_row: int, d_col: int, direction: str) -> None:
        self.direction = direction
        row, col = self._idx_to_rc(self.cursor)
        w = self.puzzle.width
        h = self.puzzle.height
        total = w * h

        wrapped = False
        for offset in range(1, total + 1):
            next_row, next_col, step_wrapped = self._next_scan_position(
                row=row,
                col=col,
                d_row=d_row,
                d_col=d_col,
                offset=offset,
            )
            wrapped = wrapped or step_wrapped
            candidate = self._rc_to_idx(next_row, next_col)
            if self._is_block(candidate):
                continue

            if wrapped and self._jump_to_first_partially_unfilled_alternating():
                return

            self.cursor = candidate
            break

        self._sync_selected_to_cursor()
        if self.selected and not self._entry_has_blank(self.selected):
            self._jump_to_next_partially_unfilled_from_selected(step=1)

    def cycle_clue(self, step: int) -> None:
        pool = self.across_entries if self.direction == "A" else self.down_entries
        if not pool:
            return

        current = self._entry_for_cell(self.cursor, self.direction) or self.selected
        if not current or current.direction != self.direction:
            current = pool[0]

        try:
            idx = pool.index(current)
        except ValueError:
            idx = 0

        wrapped = (step > 0 and idx == len(pool) - 1) or (step < 0 and idx == 0)
        if wrapped:
            other_pool = self.down_entries if self.direction == "A" else self.across_entries
            if other_pool:
                target = other_pool[0] if step > 0 else other_pool[-1]
            else:
                target = pool[(idx + step) % len(pool)]
        else:
            target = pool[(idx + step) % len(pool)]

        self.selected = target
        self.cursor = target.cells[0]
        if not self._entry_has_blank(target):
            self._jump_to_next_partially_unfilled_from_selected(step=step)

    def input_letter(self, ch: str) -> None:
        if not ch.isalpha() or self._is_block(self.cursor):
            return

        self._sync_selected_to_cursor()
        current_entry = self.selected
        self.user[self.cursor] = ch.upper()
        self._step_within_entry(1)
        if current_entry and not self._entry_has_blank(current_entry):
            self.selected = current_entry
            self.direction = current_entry.direction
            self._jump_to_next_partially_unfilled_from_selected(step=1)

    def backspace(self) -> None:
        if self._is_block(self.cursor):
            return

        if self.user[self.cursor] != " ":
            self.user[self.cursor] = " "
            return

        self._step_within_entry(-1)
        if not self._is_block(self.cursor):
            self.user[self.cursor] = " "

    def _step_within_entry(self, step: int) -> None:
        self._sync_selected_to_cursor()
        if not self.selected or self.cursor not in self.selected.cells:
            return

        pos = self.selected.cells.index(self.cursor)
        next_pos = pos + step
        if 0 <= next_pos < len(self.selected.cells):
            self.cursor = self.selected.cells[next_pos]

    def status(self) -> tuple[int, int, bool]:
        wrong = 0
        empty = 0
        for i, sol in enumerate(self.puzzle.solution):
            if sol == ".":
                continue
            cur = self.user[i]
            if cur == " ":
                empty += 1
            elif cur != sol:
                wrong += 1
        return wrong, empty, wrong == 0 and empty == 0


class KeyReader:
    def __init__(self) -> None:
        self.is_windows = os.name == "nt"
        self.fd: int | None = None
        self.old_settings: list[int] | None = None

    def __enter__(self) -> KeyReader:
        if self.is_windows:
            return self

        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.is_windows:
            return

        if self.fd is not None and self.old_settings is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def read_key(self) -> str:
        if self.is_windows:
            return self._read_windows_key()
        return self._read_posix_key()

    def _read_windows_key(self) -> str:
        import msvcrt

        ch = msvcrt.getwch()
        if ch in {"\x00", "\xe0"}:
            code = msvcrt.getwch()
            return {
                "H": "UP",
                "P": "DOWN",
                "K": "LEFT",
                "M": "RIGHT",
                "S": "DELETE",
                "\x0f": "SHIFT_TAB",
            }.get(code, "UNKNOWN")

        if ch == "\t":
            return "TAB"
        if ch == "\x0f":
            return "SHIFT_TAB"
        if ch in {"\x08", "\x7f"}:
            return "BACKSPACE"
        if ch in {"\r", "\n"}:
            return "ENTER"
        if ch == "\x1b":
            return "ESC"
        if ch == "\x03":
            return "QUIT"
        if ch and ch.isprintable():
            return f"CHAR:{ch}"
        return "UNKNOWN"

    def _read_posix_key(self) -> str:
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = ""
            while True:
                r, _, _ = select.select([sys.stdin], [], [], 0.01)
                if not r:
                    break
                seq += sys.stdin.read(1)

            full = "\x1b" + seq
            return {
                "\x1b[A": "UP",
                "\x1b[B": "DOWN",
                "\x1b[C": "RIGHT",
                "\x1b[D": "LEFT",
                "\x1b[Z": "SHIFT_TAB",
            }.get(full, "ESC")

        if ch == "\t":
            return "TAB"
        if ch in {"\x7f", "\x08"}:
            return "BACKSPACE"
        if ch in {"\r", "\n"}:
            return "ENTER"
        if ch == "\x03":
            return "QUIT"
        if ch and ch.isprintable():
            return f"CHAR:{ch}"
        return "UNKNOWN"


class TerminalUI:
    def __init__(self) -> None:
        self.alt_screen = True

    def __enter__(self) -> TerminalUI:
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H")
        sys.stdout.flush()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()

    def draw(self, text: str) -> None:
        sys.stdout.write("\x1b[H\x1b[2J")
        sys.stdout.write(text)
        sys.stdout.flush()


def _render_board(game: CrosswordGame) -> list[str]:
    w = game.puzzle.width
    h = game.puzzle.height
    selected_cells = set(game.selected.cells) if game.selected else set()
    lines: list[str] = []

    for r in range(h):
        cells: list[str] = []
        for c in range(w):
            idx = (r * w) + c
            in_selected = idx in selected_cells
            if game.user[idx] == ".":
                glyph = "▇"
            elif game.user[idx] == " ":
                glyph = "·"
            else:
                glyph = game.user[idx]

            if idx == game.cursor and game.user[idx] != ".":
                glyph = f"\x1b[7m{glyph}\x1b[0m"
            elif game.user[idx] != "." and in_selected:
                glyph = f"\x1b[48;5;238m{glyph}\x1b[0m"

            cells.append(glyph)

        lines.append(" ".join(cells))

    return lines


def _fit(line: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(line) <= width:
        return line
    if width <= 3:
        return line[:width]
    return line[: width - 3] + "..."


def _render_screen(game: CrosswordGame, message: str) -> str:
    term_width = shutil.get_terminal_size((120, 40)).columns
    wrong, empty, solved = game.status()

    selected = game.selected
    clue = ""
    if selected:
        clue = f"{selected.key} [{len(selected.cells)}]: {selected.clue}"

    lines: list[str] = []
    wrong_text = str(wrong) if game.show_wrong_progress else "hidden"
    lines.append(_fit(f"Progress: empty={empty}, wrong={wrong_text} (press \\ to toggle)", term_width))
    lines.append(_fit(f"Clue: {clue}", term_width))
    lines.append(_fit(message, term_width))
    lines.append("")

    lines.extend(_render_board(game))

    if solved:
        lines.append("")
        lines.append("Solved!")

    return "\n".join(_fit(line, term_width) for line in lines)


def play(puz_path: str | Path) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError("Interactive mode requires a TTY terminal.")

    puzzle = load_puz(puz_path)
    game = CrosswordGame(puzzle)
    message = "Ready."

    with TerminalUI() as ui, KeyReader() as reader:
        while True:
            game._sync_selected_to_cursor()
            screen = _render_screen(game, message)
            message = ""
            ui.draw(screen)

            key = reader.read_key()

            if key == "QUIT":
                return
            if key == "UP":
                if game.direction == "A":
                    game.switch_direction_at_cursor("D")
                else:
                    game.move_cursor(-1, 0, "D")
                continue
            if key == "DOWN":
                if game.direction == "A":
                    game.switch_direction_at_cursor("D")
                else:
                    game.move_cursor(1, 0, "D")
                continue
            if key == "LEFT":
                if game.direction == "D":
                    game.switch_direction_at_cursor("A")
                else:
                    game.move_cursor(0, -1, "A")
                continue
            if key == "RIGHT":
                if game.direction == "D":
                    game.switch_direction_at_cursor("A")
                else:
                    game.move_cursor(0, 1, "A")
                continue
            if key == "TAB":
                game.cycle_clue(1)
                continue
            if key == "SHIFT_TAB":
                game.cycle_clue(-1)
                continue
            if key == "BACKSPACE":
                game.backspace()
                continue
            if key.startswith("CHAR:"):
                char = key.split(":", 1)[1]
                if char == "\\":
                    enabled = game.toggle_wrong_progress()
                    message = f"Wrong counter {'on' if enabled else 'hidden'}."
                    continue
                if char.isalpha():
                    game.input_letter(char)
                    continue
                message = "Only letters are fillable."
                continue

            message = "Unrecognized key."
