# crossword-cli

Terminal crossword game for `.puz` files.

## Run

```bash
python -m crossword_cli path/to/puzzle.puz
```

or, after install:

```bash
pip install -e .
crossword-cli path/to/puzzle.puz
```

## Controls

- `Arrow keys`: move cursor and set direction (`left/right` = across, `up/down` = down)
- `Arrow keys` on opposite direction: switch direction at current square (across <-> down) without moving
- `Tab`: jump to next clue in current direction
- `Shift+Tab`: jump to previous clue in current direction
- `Letters`: fill current cell and advance
- `Backspace`: clear current cell (or move backward and clear)
- `\`: toggle the `wrong` progress counter visibility
- `Ctrl+C`: quit

The board renders with borders and square symbols: `■` for blocks and `□` for empty cells.
