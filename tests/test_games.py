from __future__ import annotations

import io
import random
import tempfile
import unittest
from pathlib import Path

from rich.cells import cell_len
from rich.console import Console

from arcade.input import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESC,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_SPACE,
    KEY_UP,
    parse_escape_bytes,
)
from arcade.invaders import Bullet, SpaceInvadersGame
from arcade.scores import ScoreStore
from arcade.snake import DIR_DOWN, DIR_LEFT, DIR_RIGHT, DIR_UP, SnakeGame
from arcade.ui import render_main_menu


class InputParsingTests(unittest.TestCase):
    def test_csi_and_ss3_arrows(self) -> None:
        raw = b"\x1b[A\x1b[B\x1b[C\x1b[D\x1bOA\x1bOB"
        self.assertEqual(
            parse_escape_bytes(raw),
            [KEY_UP, KEY_DOWN, KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_DOWN],
        )

    def test_mixed_keys_and_esc(self) -> None:
        raw = b"w \r\x1bq"
        self.assertEqual(
            parse_escape_bytes(raw),
            ["w", KEY_SPACE, KEY_ENTER, KEY_ESC, "q"],
        )


class ScoreStoreTests(unittest.TestCase):
    def test_record_persists_sorts_and_caps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scores.json"
            store = ScoreStore(path=path, max_per_game=3)
            self.assertTrue(store.record("snake", 40, "Normale", "Len 7"))
            self.assertFalse(store.record("snake", 20, "Facile", "Len 5"))
            self.assertTrue(store.record("snake", 90, "Difficile", "Len 12"))
            self.assertFalse(store.record("snake", 50, "Normale", "Len 8"))

            reloaded = ScoreStore(path=path, max_per_game=3)
            top = reloaded.top_scores("snake")
            self.assertEqual([e.score for e in top], [90, 50, 40])
            self.assertEqual(reloaded.best_score("snake"), 90)


class SnakeGameTests(unittest.TestCase):
    def test_eating_apple_grows_snake_and_scores(self) -> None:
        game = SnakeGame(width=12, height=10, rng=random.Random(42))
        hx, hy = game.snake[0]
        game.food = (hx + 1, hy)
        initial_len = len(game.snake)
        game.step()
        self.assertEqual(game.score, 10)
        self.assertEqual(len(game.snake), initial_len + 1)
        self.assertFalse(game.game_over)

    def test_opposite_direction_ignored_and_corner_queue_works(self) -> None:
        game = SnakeGame(width=12, height=10, rng=random.Random(1))
        game.queue_direction(DIR_LEFT)  # opposite of initial RIGHT
        game.step()
        self.assertEqual(game.direction, DIR_RIGHT)

        game.queue_direction(DIR_UP)
        game.queue_direction(DIR_LEFT)
        game.step()
        self.assertEqual(game.direction, DIR_UP)
        game.step()
        self.assertEqual(game.direction, DIR_LEFT)

    def test_wall_collision_triggers_game_over(self) -> None:
        game = SnakeGame(width=8, height=8, rng=random.Random(2))
        for _ in range(15):
            game.step()
            if game.game_over:
                break
        self.assertTrue(game.game_over)

    def test_board_line_widths_consistent(self) -> None:
        game = SnakeGame(width=20, height=12, rng=random.Random(3))
        lines = game.render_board_lines()
        self.assertEqual(len(lines), 12)
        for line in lines:
            self.assertEqual(cell_len(line.plain), 40)

        console = Console(file=io.StringIO(), width=90, height=30, record=True)
        console.print(game.render())
        self.assertIn("NEON SNAKE", console.export_text())


class SpaceInvadersTests(unittest.TestCase):
    def test_player_shoots_alien_and_scores(self) -> None:
        game = SpaceInvadersGame(rng=random.Random(7))
        target = game.alive_aliens[-1]
        game.shields.clear()
        game.player_x = target.x + 1
        game.bullets.append(Bullet(x=target.x + 1, y=target.y + 1, dy=-1))
        game.step()
        self.assertFalse(target.alive)
        self.assertGreater(game.score, 0)

    def test_clearing_wave_advances_wave(self) -> None:
        game = SpaceInvadersGame(rng=random.Random(8))
        for a in game.aliens:
            a.alive = False
        game.step()
        self.assertEqual(game.wave, 2)
        self.assertEqual(len(game.alive_aliens), 32)
        self.assertEqual(game.score, 100)

    def test_shield_absorbs_bullet(self) -> None:
        game = SpaceInvadersGame(rng=random.Random(9))
        sx, sy = next(iter(game.shields))
        game.bullets.append(Bullet(x=sx, y=sy + 1, dy=-1))
        game.step()
        self.assertNotIn((sx, sy), game.shields)

    def test_board_line_widths_and_menu_render(self) -> None:
        game = SpaceInvadersGame(rng=random.Random(10))
        lines = game.render_board_lines()
        self.assertEqual(len(lines), game.height)
        for line in lines:
            self.assertEqual(cell_len(line.plain), game.width)

        console = Console(file=io.StringIO(), width=100, height=34, record=True)
        console.print(game.render())
        self.assertIn("SPACE INVADERS", console.export_text())

        with tempfile.TemporaryDirectory() as tmp:
            store = ScoreStore(path=Path(tmp) / "scores.json")
            menu_console = Console(file=io.StringIO(), width=100, height=34, record=True)
            menu_console.print(render_main_menu(0, "Normale", store))
            text = menu_console.export_text()
            self.assertIn("NEON SNAKE", text)
            self.assertIn("SPACE INVADERS", text)


if __name__ == "__main__":
    unittest.main()
