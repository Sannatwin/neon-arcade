from __future__ import annotations

import random
import time
from collections import deque
from typing import Deque, Dict, Optional, Set, Tuple

from rich import box
from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from arcade.input import (
    KEY_DOWN,
    KEY_ESC,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_UP,
    KeyboardReader,
)
from arcade.scores import ScoreStore
from arcade.ui import build_hud, build_status_banner

Point = Tuple[int, int]

DIR_UP: Point = (0, -1)
DIR_DOWN: Point = (0, 1)
DIR_LEFT: Point = (-1, 0)
DIR_RIGHT: Point = (1, 0)

OPPOSITE: Dict[Point, Point] = {
    DIR_UP: DIR_DOWN,
    DIR_DOWN: DIR_UP,
    DIR_LEFT: DIR_RIGHT,
    DIR_RIGHT: DIR_LEFT,
}

DIFFICULTY_TICK: Dict[str, Tuple[float, float]] = {
    # (initial_tick_seconds, min_tick_seconds)
    "Facile": (0.16, 0.085),
    "Normale": (0.125, 0.065),
    "Difficile": (0.095, 0.048),
}


class SnakeGame:
    """Real-time Neon Snake game logic and Rich renderer."""

    def __init__(
        self,
        width: int = 26,
        height: int = 16,
        difficulty: str = "Normale",
        best_score: int = 0,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.width = width
        self.height = height
        self.difficulty = difficulty if difficulty in DIFFICULTY_TICK else "Normale"
        self.best_score = best_score
        self._rng = rng or random.Random()
        self.reset()

    def reset(self) -> None:
        cx = self.width // 2
        cy = self.height // 2
        self.snake: Deque[Point] = deque([(cx, cy), (cx - 1, cy), (cx - 2, cy)])
        self.direction: Point = DIR_RIGHT
        self._dir_queue: Deque[Point] = deque()
        self.score: int = 0
        self.apples_eaten: int = 0
        self.game_over: bool = False
        self.won: bool = False
        self.paused: bool = False
        self.new_record: bool = False
        self.bonus_food: Optional[Point] = None
        self.bonus_ttl: int = 0
        self.food: Optional[Point] = None
        self.food = self._spawn_cell()

    @property
    def tick_interval(self) -> float:
        start, minimum = DIFFICULTY_TICK[self.difficulty]
        speedup = self.apples_eaten * 0.003
        return max(minimum, start - speedup)

    @property
    def speed_level(self) -> int:
        return 1 + self.apples_eaten // 4

    def _occupied(self) -> Set[Point]:
        occ = set(self.snake)
        if self.food is not None:
            occ.add(self.food)
        if self.bonus_food is not None:
            occ.add(self.bonus_food)
        return occ

    def _spawn_cell(self) -> Optional[Point]:
        occ = self._occupied()
        free = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if (x, y) not in occ
        ]
        if not free:
            return None
        return self._rng.choice(free)

    def queue_direction(self, new_dir: Point) -> None:
        if self.game_over or self.paused:
            return
        last_planned = self._dir_queue[-1] if self._dir_queue else self.direction
        if new_dir == last_planned or new_dir == OPPOSITE[last_planned]:
            return
        if len(self._dir_queue) < 2:
            self._dir_queue.append(new_dir)

    def step(self) -> None:
        """Advance the game state by one tick."""
        if self.game_over or self.paused:
            return

        if self._dir_queue:
            self.direction = self._dir_queue.popleft()

        hx, hy = self.snake[0]
        dx, dy = self.direction
        nx, ny = hx + dx, hy + dy

        # Wall collision
        if not (0 <= nx < self.width and 0 <= ny < self.height):
            self.game_over = True
            return

        new_head = (nx, ny)
        ate_food = new_head == self.food
        ate_bonus = new_head == self.bonus_food

        # Tail vacates its cell unless growing this tick
        body_to_check = list(self.snake) if (ate_food or ate_bonus) else list(self.snake)[:-1]
        if new_head in body_to_check:
            self.game_over = True
            return

        self.snake.appendleft(new_head)

        if ate_food:
            self.score += 10
            self.apples_eaten += 1
            self.food = self._spawn_cell()
            if self.food is None:
                self.won = True
                self.game_over = True
                return
            if self.apples_eaten % 4 == 0 and self.bonus_food is None:
                self.bonus_food = self._spawn_cell()
                self.bonus_ttl = 36
        elif ate_bonus:
            self.score += 35
            self.bonus_food = None
            self.bonus_ttl = 0
        else:
            self.snake.pop()

        if self.bonus_food is not None:
            self.bonus_ttl -= 1
            if self.bonus_ttl <= 0:
                self.bonus_food = None
                self.bonus_ttl = 0

        if self.score > self.best_score:
            self.best_score = self.score
            self.new_record = True

    def render_board_lines(self) -> list[Text]:
        snake_list = list(self.snake)
        head = snake_list[0]
        body_index = {pos: idx for idx, pos in enumerate(snake_list)}
        tail_idx = len(snake_list) - 1

        lines: list[Text] = []
        for y in range(self.height):
            row = Text()
            for x in range(self.width):
                pos = (x, y)
                if pos == head:
                    head_style = "bold bright_red" if self.game_over and not self.won else "bold bright_cyan"
                    row.append("██", style=head_style)
                elif pos in body_index:
                    idx = body_index[pos]
                    if idx == tail_idx:
                        row.append("▓▓", style="green")
                    elif idx <= 3:
                        row.append("██", style="bold bright_green")
                    else:
                        row.append("██", style="green")
                elif pos == self.food:
                    row.append("<>", style="bold bright_red")
                elif pos == self.bonus_food:
                    style = "bold bright_yellow" if self.bonus_ttl > 10 or self.bonus_ttl % 2 == 0 else "yellow"
                    row.append("**", style=style)
                else:
                    dot = "· " if (x + y) % 2 == 0 else "  "
                    row.append(dot, style="grey23")
            lines.append(row)
        return lines

    def render(self) -> RenderableType:
        stats = [
            ("Punti", str(self.score), "bright_yellow"),
            ("Record", str(self.best_score), "bright_magenta"),
            ("Lunghezza", str(len(self.snake)), "bright_green"),
            ("Vel.", f"x{self.speed_level}", "bright_cyan"),
        ]
        if self.bonus_food is not None:
            stats.append(("Bonus **", f"{self.bonus_ttl}", "bright_yellow"))

        hud = build_hud(f"NEON SNAKE ({self.difficulty})", "bright_green", stats)

        board_text = Text("\n").join(self.render_board_lines())
        border_color = "bright_red" if self.game_over and not self.won else "bright_green"
        board_panel = Panel(
            board_text,
            border_style=border_color,
            box=box.HEAVY,
            padding=(0, 0),
        )

        controls = Text.assemble(
            (" [", "dim"),
            ("Frecce / WASD", "bold bright_cyan"),
            ("] Muovi  ", "dim"),
            ("[", "dim"),
            ("P", "bold bright_yellow"),
            ("] Pausa  ", "dim"),
            ("[", "dim"),
            ("R", "bold bright_green"),
            ("] Rigioca  ", "dim"),
            ("[", "dim"),
            ("Q / Esc", "bold bright_red"),
            ("] Menu ", "dim"),
        )

        elements = [Align.center(hud), Align.center(board_panel)]

        if self.game_over:
            if self.won:
                headline = "VITTORIA PERFETTA!"
                color = "bright_yellow"
            elif self.new_record:
                headline = "GAME OVER - NUOVO RECORD!"
                color = "bright_yellow"
            else:
                headline = "GAME OVER"
                color = "bright_red"
            elements.append(
                Align.center(
                    build_status_banner(
                        headline=headline,
                        details=f"Punteggio finale: {self.score}  |  Lunghezza: {len(self.snake)}",
                        color=color,
                        hint="Premi [R] per rigiocare oppure [Q] / [Esc] per il menu",
                    )
                )
            )
        elif self.paused:
            elements.append(
                Align.center(
                    build_status_banner(
                        headline="IN PAUSA",
                        details="Prendi fiato prima di ripartire!",
                        color="bright_yellow",
                        hint="Premi [P] per continuare  |  [R] Rigioca  |  [Q] Menu",
                    )
                )
            )

        elements.append(Align.center(controls))
        return Align.center(Group(*elements), vertical="middle")


def run_snake(
    console: Console,
    reader: KeyboardReader,
    scores: ScoreStore,
    difficulty: str,
) -> None:
    """Run the interactive real-time Neon Snake game loop."""
    game = SnakeGame(
        difficulty=difficulty,
        best_score=scores.best_score("snake"),
    )
    score_saved = False

    key_to_dir = {
        KEY_UP: DIR_UP,
        "w": DIR_UP,
        KEY_DOWN: DIR_DOWN,
        "s": DIR_DOWN,
        KEY_LEFT: DIR_LEFT,
        "a": DIR_LEFT,
        KEY_RIGHT: DIR_RIGHT,
        "d": DIR_RIGHT,
    }

    last_tick = time.monotonic()

    with Live(game.render(), console=console, screen=True, auto_refresh=False) as live:
        while True:
            keys = reader.poll_keys(timeout=0.015)
            dirty = False

            for key in keys:
                if key in ("q", KEY_ESC):
                    if not score_saved and game.score > 0:
                        scores.record(
                            "snake",
                            game.score,
                            difficulty,
                            detail=f"Len {len(game.snake)}",
                        )
                    return
                if key == "r":
                    game.best_score = scores.best_score("snake")
                    game.reset()
                    score_saved = False
                    last_tick = time.monotonic()
                    dirty = True
                elif key == "p" and not game.game_over:
                    game.paused = not game.paused
                    last_tick = time.monotonic()
                    dirty = True
                elif key in key_to_dir:
                    game.queue_direction(key_to_dir[key])

            now = time.monotonic()
            if not game.paused and not game.game_over:
                if now - last_tick >= game.tick_interval:
                    last_tick = now
                    game.step()
                    dirty = True

            if game.game_over and not score_saved:
                if game.score > 0:
                    scores.record(
                        "snake",
                        game.score,
                        difficulty,
                        detail=f"Len {len(game.snake)}",
                    )
                score_saved = True
                dirty = True

            if dirty:
                live.update(game.render(), refresh=True)
