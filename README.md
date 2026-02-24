# crossword-cli

Terminal crossword game for `.puz` files.

## Run

```bash
pip install -e .
crossword-cli path/to/puzzle.puz
```

## Controls

- `Arrow keys`: move cursor and set direction (`left/right` = across, `up/down` = down)
- `Tab`: jump to next clue
- `Shift+Tab`: jump to previous clue
- `Letters`: fill current cell
- `Backspace`: clear current cell
- `\`: toggle `wrong` progress counter visibility
- `Ctrl+C`: quit
