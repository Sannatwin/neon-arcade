from __future__ import annotations

import argparse
import sys
from typing import Optional

from rich.console import Console
from rich.live import Live

from arcade.input import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESC,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_SPACE,
    KEY_UP,
    KeyboardReader,
)
from arcade.invaders import run_invaders
from arcade.scores import ScoreStore
from arcade.snake import run_snake
from arcade.ui import DIFFICULTIES, render_main_menu


def run_arcade(
    initial_game: Optional[str] = None,
    initial_difficulty: str = "Normale",
) -> int:
    console = Console()
    scores = ScoreStore()

    if not sys.stdin.isatty():
        console.print(
            "[bold bright_yellow]Neon Arcade richiede un terminale interattivo (TTY).[/]\n"
            "Avvialo dal tuo terminale con: [bold bright_cyan]python3 main.py[/]"
        )
        return 1

    diff_idx = (
        DIFFICULTIES.index(initial_difficulty)
        if initial_difficulty in DIFFICULTIES
        else 1
    )
    selected = 0

    try:
        with KeyboardReader() as reader:
            if initial_game == "snake":
                run_snake(console, reader, scores, DIFFICULTIES[diff_idx])
                return 0
            if initial_game == "invaders":
                run_invaders(console, reader, scores, DIFFICULTIES[diff_idx])
                return 0

            while True:
                action = _run_menu_loop(console, reader, scores, selected, diff_idx)
                if action is None:
                    break
                choice, diff_idx = action
                selected = choice

                if choice == 0:
                    run_snake(console, reader, scores, DIFFICULTIES[diff_idx])
                elif choice == 1:
                    run_invaders(console, reader, scores, DIFFICULTIES[diff_idx])
                elif choice == 3:
                    break
    except KeyboardInterrupt:
        pass

    console.print("\n[bold bright_cyan]Grazie per aver giocato a Neon Arcade![/]")
    return 0


def _run_menu_loop(
    console: Console,
    reader: KeyboardReader,
    scores: ScoreStore,
    selected: int,
    diff_idx: int,
) -> Optional[tuple[int, int]]:
    num_items = 4
    with Live(
        render_main_menu(selected, DIFFICULTIES[diff_idx], scores),
        console=console,
        screen=True,
        auto_refresh=False,
    ) as live:
        while True:
            key = reader.wait_key(timeout=0.25)
            if key is None:
                continue

            if key in ("q", KEY_ESC):
                return None
            if key in (KEY_UP, "w"):
                selected = (selected - 1) % num_items
            elif key in (KEY_DOWN, "s"):
                selected = (selected + 1) % num_items
            elif key in (KEY_LEFT, "a"):
                diff_idx = (diff_idx - 1) % len(DIFFICULTIES)
            elif key in (KEY_RIGHT, "d"):
                diff_idx = (diff_idx + 1) % len(DIFFICULTIES)
            elif key in (KEY_ENTER, KEY_SPACE):
                if selected == 2:
                    diff_idx = (diff_idx + 1) % len(DIFFICULTIES)
                else:
                    return (selected, diff_idx)
            elif key == "1":
                return (0, diff_idx)
            elif key == "2":
                return (1, diff_idx)

            live.update(
                render_main_menu(selected, DIFFICULTIES[diff_idx], scores),
                refresh=True,
            )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="neon-arcade",
        description="Neon Arcade - Giochi arcade in tempo reale nel terminale con Rich",
    )
    parser.add_argument(
        "--game",
        choices=["snake", "invaders"],
        default=None,
        help="Avvia direttamente un gioco specifico saltando il menu",
    )
    parser.add_argument(
        "--difficulty",
        choices=list(DIFFICULTIES),
        default="Normale",
        help="Difficolta iniziale (default: Normale)",
    )
    args = parser.parse_args(argv)
    return run_arcade(initial_game=args.game, initial_difficulty=args.difficulty)


if __name__ == "__main__":
    raise SystemExit(main())
