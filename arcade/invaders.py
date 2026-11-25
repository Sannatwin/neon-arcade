from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from rich import box
from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from arcade.input import (
    KEY_ESC,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_SPACE,
    KEY_UP,
    KeyboardReader,
)
from arcade.scores import ScoreStore
from arcade.ui import build_hud, build_status_banner


DIFFICULTY_PARAMS: Dict[str, Dict[str, float]] = {
    "Facile": {
        "march_base": 14,
        "enemy_fire_prob": 0.045,
        "lives": 4,
    },
    "Normale": {
        "march_base": 10,
        "enemy_fire_prob": 0.075,
        "lives": 3,
    },
    "Difficile": {
        "march_base": 7,
        "enemy_fire_prob": 0.11,
        "lives": 3,
    },
}

ALIEN_ROWS: List[Tuple[str, str, int, str]] = [
    # (sprite_frame_0, sprite_frame_1, points, style)
    ("<o>", "{o}", 30, "bold bright_magenta"),
    ("/W\\", "\\M/", 20, "bold bright_yellow"),
    ("=H=", "-H-", 10, "bold bright_green"),
    ("=H=", "-H-", 10, "bold green"),
]


@dataclass
class Alien:
    x: int
    y: int
    row_type: int
    alive: bool = True


@dataclass
class Bullet:
    x: int
    y: int
    dy: int  # -1 player, +1 enemy


@dataclass
class Spark:
    x: int
    y: int
    ttl: int
    text: str
    style: str


class SpaceInvadersGame:
    """Real-time Space Invaders game logic and Rich renderer."""

    def __init__(
        self,
        width: int = 56,
        height: int = 21,
        difficulty: str = "Normale",
        best_score: int = 0,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.width = width
        self.height = height
        self.difficulty = difficulty if difficulty in DIFFICULTY_PARAMS else "Normale"
        self.best_score = best_score
        self._rng = rng or random.Random()
        self.tick_seconds = 0.05  # 20 FPS smooth arcade loop
        self.reset()

    def reset(self) -> None:
        params = DIFFICULTY_PARAMS[self.difficulty]
        self.score: int = 0
        self.wave: int = 1
        self.lives: int = int(params["lives"])
        self.player_x: int = self.width // 2
        self.player_y: int = self.height - 2
        self.player_cooldown: int = 0
        self.invulnerable_ticks: int = 0
        self.frame: int = 0
        self.game_over: bool = False
        self.paused: bool = False
        self.new_record: bool = False
        self.bullets: List[Bullet] = []
        self.sparks: List[Spark] = []
        self.ufo_x: Optional[int] = None
        self.ufo_dir: int = 1
        self.shields: Set[Tuple[int, int]] = set()
        self._build_shields()
        self._spawn_wave()

    def _build_shields(self) -> None:
        self.shields.clear()
        shield_y = self.height - 5
        shield_positions = [8, 20, 32, 44]
        for sx in shield_positions:
            for dx in range(5):
                self.shields.add((sx + dx, shield_y))
                if dx != 2:  # classic arch gap in bottom row
                    self.shields.add((sx + dx, shield_y + 1))

    def _spawn_wave(self) -> None:
        self.aliens: List[Alien] = []
        self.alien_dir: int = 1
        self.alien_anim: int = 0
        self.march_counter: int = 0
        start_y = min(5, 2 + (self.wave - 1) // 2)
        for r in range(4):
            for c in range(8):
                ax = 6 + c * 5
                ay = start_y + r * 2
                self.aliens.append(Alien(x=ax, y=ay, row_type=r))

    @property
    def alive_aliens(self) -> List[Alien]:
        return [a for a in self.aliens if a.alive]

    def move_player(self, dx: int) -> None:
        if self.game_over or self.paused:
            return
        self.player_x = max(2, min(self.width - 3, self.player_x + dx))

    def fire_player(self) -> None:
        if self.game_over or self.paused or self.player_cooldown > 0:
            return
        active_player_bullets = sum(1 for b in self.bullets if b.dy < 0)
        if active_player_bullets >= 2:
            return
        self.bullets.append(Bullet(x=self.player_x, y=self.player_y - 1, dy=-1))
        self.player_cooldown = 4

    def step(self) -> None:
        """Advance Space Invaders by one frame (~50ms)."""
        if self.game_over or self.paused:
            return

        self.frame += 1
        if self.player_cooldown > 0:
            self.player_cooldown -= 1
        if self.invulnerable_ticks > 0:
            self.invulnerable_ticks -= 1

        # Decay explosion sparks
        self.sparks = [
            Spark(s.x, s.y, s.ttl - 1, s.text, s.style)
            for s in self.sparks
            if s.ttl > 1
        ]

        # Move UFO
        self._step_ufo()

        # Move bullets & check collisions
        self._step_bullets()

        if self.game_over:
            return

        # Check wave clear
        if not self.alive_aliens:
            self.wave += 1
            self._add_score(100)
            self.bullets.clear()
            self._build_shields()
            self._spawn_wave()
            self.sparks.append(
                Spark(
                    x=self.width // 2 - 5,
                    y=self.height // 2,
                    ttl=16,
                    text=f"ONDATA {self.wave}!",
                    style="bold bright_cyan",
                )
            )
            return

        # March aliens with progressive acceleration as count drops
        params = DIFFICULTY_PARAMS[self.difficulty]
        alive_count = len(self.alive_aliens)
        ratio = alive_count / 32.0
        wave_bonus = max(0, self.wave - 1)
        march_interval = max(
            2, int(round(params["march_base"] * (0.35 + 0.65 * ratio))) - wave_bonus
        )

        self.march_counter += 1
        if self.march_counter >= march_interval:
            self.march_counter = 0
            self._march_aliens()

        # Random enemy fire
        enemy_bullets = sum(1 for b in self.bullets if b.dy > 0)
        max_enemy_bullets = min(6, 2 + self.wave)
        if enemy_bullets < max_enemy_bullets and self._rng.random() < params["enemy_fire_prob"]:
            self._fire_enemy()

    def _add_score(self, points: int) -> None:
        self.score += points
        if self.score > self.best_score:
            self.best_score = self.score
            self.new_record = True

    def _step_ufo(self) -> None:
        if self.ufo_x is None:
            if self.frame > 80 and self._rng.random() < 0.005:
                self.ufo_dir = self._rng.choice([-1, 1])
                self.ufo_x = 1 if self.ufo_dir == 1 else self.width - 6
        elif self.frame % 2 == 0:
            self.ufo_x += self.ufo_dir
            if self.ufo_x < 0 or self.ufo_x > self.width - 5:
                self.ufo_x = None

    def _march_aliens(self) -> None:
        alive = self.alive_aliens
        if not alive:
            return
        self.alien_anim = 1 - self.alien_anim

        hit_edge = any(
            (a.x + self.alien_dir < 1) or (a.x + 2 + self.alien_dir >= self.width - 1)
            for a in alive
        )
        if hit_edge:
            self.alien_dir *= -1
            for a in alive:
                a.y += 1
        else:
            for a in alive:
                a.x += self.alien_dir

        # Clear shields touched by aliens and check invasion line
        for a in alive:
            for dx in range(3):
                self.shields.discard((a.x + dx, a.y))
            if a.y >= self.player_y:
                self.lives = 0
                self.game_over = True
                return

    def _fire_enemy(self) -> None:
        # Pick bottom-most alive alien per column
        bottom_by_col: Dict[int, Alien] = {}
        for a in self.alive_aliens:
            col = a.x // 5
            if col not in bottom_by_col or a.y > bottom_by_col[col].y:
                bottom_by_col[col] = a
        if not bottom_by_col:
            return
        shooter = self._rng.choice(list(bottom_by_col.values()))
        self.bullets.append(Bullet(x=shooter.x + 1, y=shooter.y + 1, dy=1))

    def _step_bullets(self) -> None:
        remaining: List[Bullet] = []
        for b in self.bullets:
            # Enemy bullets move slightly slower (every 2 frames) for fair dodging
            if b.dy > 0 and self.frame % 2 != 0:
                remaining.append(b)
                continue

            b.y += b.dy
            if not (0 <= b.y < self.height):
                continue

            # Shield collision
            if (b.x, b.y) in self.shields:
                self.shields.discard((b.x, b.y))
                self.sparks.append(Spark(b.x, b.y, 3, "*", "bold bright_cyan"))
                continue

            if b.dy < 0:
                # Check UFO hit
                if self.ufo_x is not None and b.y == 1 and self.ufo_x <= b.x <= self.ufo_x + 4:
                    self._add_score(100)
                    self.sparks.append(
                        Spark(self.ufo_x, 1, 8, "+100!", "bold bright_yellow")
                    )
                    self.ufo_x = None
                    continue

                # Check alien hit
                hit_alien: Optional[Alien] = None
                for a in self.alive_aliens:
                    if a.y == b.y and a.x <= b.x <= a.x + 2:
                        hit_alien = a
                        break
                if hit_alien is not None:
                    hit_alien.alive = False
                    pts = ALIEN_ROWS[hit_alien.row_type][2]
                    self._add_score(pts)
                    self.sparks.append(
                        Spark(hit_alien.x, hit_alien.y, 4, "*+*", "bold bright_yellow")
                    )
                    continue
            else:
                # Enemy bullet hits player
                if (
                    b.y == self.player_y
                    and self.player_x - 1 <= b.x <= self.player_x + 1
                ):
                    if self.invulnerable_ticks == 0:
                        self.lives -= 1
                        self.invulnerable_ticks = 24
                        self.sparks.append(
                            Spark(
                                self.player_x - 1,
                                self.player_y,
                                6,
                                "###",
                                "bold bright_red",
                            )
                        )
                        if self.lives <= 0:
                            self.game_over = True
                    continue

            remaining.append(b)

        # Cancel out colliding player/enemy bullets
        final_bullets: List[Bullet] = []
        used: Set[int] = set()
        for i, b1 in enumerate(remaining):
            if i in used:
                continue
            collided = False
            for j in range(i + 1, len(remaining)):
                if j in used:
                    continue
                b2 = remaining[j]
                if b1.x == b2.x and abs(b1.y - b2.y) <= 1 and b1.dy != b2.dy:
                    used.add(j)
                    collided = True
                    self.sparks.append(Spark(b1.x, b1.y, 3, "x", "bold white"))
                    break
            if not collided:
                final_bullets.append(b1)

        self.bullets = final_bullets

    def render_board_lines(self) -> List[Text]:
        grid: List[List[Tuple[str, str]]] = [
            [(" ", "") for _ in range(self.width)] for _ in range(self.height)
        ]

        # Subtle background starfield (deterministic by coordinates)
        for y in range(self.height - 2):
            for x in range(self.width):
                if (x * 17 + y * 31) % 53 == 0:
                    grid[y][x] = (".", "grey23")

        def put_str(x: int, y: int, s: str, style: str) -> None:
            if not (0 <= y < self.height):
                return
            for i, ch in enumerate(s):
                tx = x + i
                if 0 <= tx < self.width:
                    grid[y][tx] = (ch, style)

        # Ground line
        put_str(0, self.height - 1, "=" * self.width, "dim cyan")

        # Shields
        for sx, sy in self.shields:
            if 0 <= sx < self.width and 0 <= sy < self.height:
                grid[sy][sx] = ("#", "bold cyan")

        # UFO
        if self.ufo_x is not None:
            put_str(self.ufo_x, 1, "<===>", "bold bright_red")

        # Aliens
        for a in self.alive_aliens:
            s0, s1, _, style = ALIEN_ROWS[a.row_type]
            sprite = s0 if self.alien_anim == 0 else s1
            put_str(a.x, a.y, sprite, style)

        # Player ship
        if not self.game_over:
            blink_hide = self.invulnerable_ticks > 0 and (self.invulnerable_ticks % 4 < 2)
            if not blink_hide:
                put_str(self.player_x - 1, self.player_y, "/^\\", "bold bright_cyan")

        # Bullets
        for b in self.bullets:
            if 0 <= b.x < self.width and 0 <= b.y < self.height:
                if b.dy < 0:
                    grid[b.y][b.x] = ("|", "bold bright_yellow")
                else:
                    grid[b.y][b.x] = ("!", "bold bright_red")

        # Sparks (drawn on top)
        for s in self.sparks:
            put_str(s.x, s.y, s.text, s.style)

        lines: List[Text] = []
        for y in range(self.height):
            row = Text()
            for ch, style in grid[y]:
                row.append(ch, style=style)
            lines.append(row)
        return lines

    def render(self) -> RenderableType:
        lives_str = " ".join(["/^\\"] * max(0, self.lives)) if self.lives > 0 else "0"
        stats = [
            ("Punti", str(self.score), "bright_yellow"),
            ("Record", str(self.best_score), "bright_magenta"),
            ("Ondata", str(self.wave), "bright_green"),
            ("Vite", lives_str, "bright_cyan" if self.lives > 1 else "bright_red"),
        ]
        hud = build_hud(f"SPACE INVADERS ({self.difficulty})", "bright_cyan", stats)

        board_text = Text("\n").join(self.render_board_lines())
        border_color = "bright_red" if self.game_over else "bright_cyan"
        board_panel = Panel(
            board_text,
            border_style=border_color,
            box=box.HEAVY,
            padding=(0, 0),
        )

        controls = Text.assemble(
            (" [", "dim"),
            ("Sinistra/Destra o A/D", "bold bright_cyan"),
            ("] Muovi  ", "dim"),
            ("[", "dim"),
            ("Spazio / Su / W", "bold bright_yellow"),
            ("] Spara  ", "dim"),
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
            headline = "INVASIONE COMPLETATA - NUOVO RECORD!" if self.new_record else "GAME OVER"
            color = "bright_yellow" if self.new_record else "bright_red"
            elements.append(
                Align.center(
                    build_status_banner(
                        headline=headline,
                        details=f"Punteggio finale: {self.score}  |  Ondata raggiunta: {self.wave}",
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
                        details="Gli alieni attendono in orbita...",
                        color="bright_yellow",
                        hint="Premi [P] per continuare  |  [R] Rigioca  |  [Q] Menu",
                    )
                )
            )

        elements.append(Align.center(controls))
        return Align.center(Group(*elements), vertical="middle")


def run_invaders(
    console: Console,
    reader: KeyboardReader,
    scores: ScoreStore,
    difficulty: str,
) -> None:
    """Run the interactive real-time Space Invaders loop."""
    game = SpaceInvadersGame(
        difficulty=difficulty,
        best_score=scores.best_score("invaders"),
    )
    score_saved = False
    last_tick = time.monotonic()

    with Live(game.render(), console=console, screen=True, auto_refresh=False) as live:
        while True:
            keys = reader.poll_keys(timeout=0.012)
            dirty = False

            for key in keys:
                if key in ("q", KEY_ESC):
                    if not score_saved and game.score > 0:
                        scores.record(
                            "invaders",
                            game.score,
                            difficulty,
                            detail=f"Ondata {game.wave}",
                        )
                    return
                if key == "r":
                    game.best_score = scores.best_score("invaders")
                    game.reset()
                    score_saved = False
                    last_tick = time.monotonic()
                    dirty = True
                elif key == "p" and not game.game_over:
                    game.paused = not game.paused
                    last_tick = time.monotonic()
                    dirty = True
                elif key in (KEY_LEFT, "a"):
                    game.move_player(-2)
                    dirty = True
                elif key in (KEY_RIGHT, "d"):
                    game.move_player(2)
                    dirty = True
                elif key in (KEY_SPACE, KEY_UP, "w"):
                    game.fire_player()
                    dirty = True

            now = time.monotonic()
            if not game.paused and not game.game_over:
                if now - last_tick >= game.tick_seconds:
                    last_tick = now
                    game.step()
                    dirty = True

            if game.game_over and not score_saved:
                if game.score > 0:
                    scores.record(
                        "invaders",
                        game.score,
                        difficulty,
                        detail=f"Ondata {game.wave}",
                    )
                score_saved = True
                dirty = True

            if dirty:
                live.update(game.render(), refresh=True)
