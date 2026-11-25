from __future__ import annotations

from typing import List, Tuple

from rich import box
from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from arcade.scores import ScoreStore


BANNER = r"""
 _   _ _____ ___  _   _      _    ____   ____    _    ____  _____
| \ | | ____/ _ \| \ | |    / \  |  _ \ / ___|  / \  |  _ \| ____|
|  \| |  _|| | | |  \| |   / _ \ | |_) | |     / _ \ | | | |  _|
| |\  | |__| |_| | |\  |  / ___ \|  _ <| |___ / ___ \| |_| | |___
|_| \_|_____\___/|_| \_| /_/   \_\_| \_\\____/_/   \_\____/|_____|
""".strip("\n")

DIFFICULTIES: Tuple[str, ...] = ("Facile", "Normale", "Difficile")


def render_main_menu(
    selected_index: int,
    difficulty: str,
    scores: ScoreStore,
) -> RenderableType:
    """Build the Rich main menu screen."""
    logo = Text(BANNER, style="bold bright_cyan")
    subtitle = Text(
        "SALA GIOCHI DA TERMINALE  •  PYTHON + RICH",
        style="bold bright_magenta",
    )

    menu_items: List[Tuple[str, str, str]] = [
        (
            "NEON SNAKE",
            "Mangia mele energetiche e bonus dorati senza schiantarti!",
            "bright_green",
        ),
        (
            "SPACE INVADERS",
            "Difendi la Terra dalle ondate aliene dietro gli scudi laser!",
            "bright_cyan",
        ),
        (
            f"DIFFICOLTA: {difficulty.upper()}",
            "Premi Invio o Freccia Sinistra/Destra per cambiare velocita",
            "bright_yellow",
        ),
        (
            "ESCI",
            "Chiudi Neon Arcade e torna al terminale",
            "bright_red",
        ),
    ]

    menu_table = Table.grid(padding=(0, 2))
    menu_table.add_column(justify="left", no_wrap=True)
    menu_table.add_column(justify="left")

    for idx, (title, desc, color) in enumerate(menu_items):
        is_sel = idx == selected_index
        pointer = ">> " if is_sel else "   "
        title_style = f"bold reverse {color}" if is_sel else f"bold {color}"
        desc_style = "white" if is_sel else "dim"
        menu_table.add_row(
            Text(f"{pointer}{title}", style=title_style),
            Text(desc, style=desc_style),
        )

    menu_panel = Panel(
        menu_table,
        title="[bold bright_magenta]SELEZIONA UN GIOCO[/]",
        border_style="bright_magenta",
        box=box.DOUBLE,
        padding=(1, 2),
    )

    # High scores side-by-side table
    scores_grid = Table.grid(expand=False, padding=(0, 3))
    scores_grid.add_column()
    scores_grid.add_column()
    scores_grid.add_row(
        _build_score_table("TOP SNAKE", "bright_green", scores.top_scores("snake")),
        _build_score_table(
            "TOP SPACE INVADERS", "bright_cyan", scores.top_scores("invaders")
        ),
    )

    footer = Text.assemble(
        (" [", "dim"),
        ("Su/Giu o W/S", "bold bright_cyan"),
        ("] Muovi  ", "dim"),
        ("[", "dim"),
        ("Invio / Spazio", "bold bright_green"),
        ("] Avvia  ", "dim"),
        ("[", "dim"),
        ("Sinistra/Destra", "bold bright_yellow"),
        ("] Difficolta  ", "dim"),
        ("[", "dim"),
        ("Q", "bold bright_red"),
        ("] Esci ", "dim"),
    )

    content = Group(
        Align.center(logo),
        Align.center(subtitle),
        Text(""),
        Align.center(menu_panel),
        Text(""),
        Align.center(scores_grid),
        Text(""),
        Align.center(footer),
    )
    return Align.center(content, vertical="middle")


def _build_score_table(title: str, color: str, entries) -> Panel:
    table = Table(
        box=box.SIMPLE_HEAD,
        show_edge=False,
        pad_edge=False,
        header_style=f"bold {color}",
    )
    table.add_column("#", justify="right", width=2)
    table.add_column("Punti", justify="right", width=7)
    table.add_column("Livello", justify="left", width=9)
    table.add_column("Info", justify="left", width=11)

    if not entries:
        table.add_row("-", "0", "-", "[dim]Nessuno[/]")
    else:
        for i, entry in enumerate(entries, start=1):
            row_style = "bold bright_yellow" if i == 1 else "white"
            table.add_row(
                str(i),
                str(entry.score),
                entry.difficulty,
                entry.detail or entry.date,
                style=row_style,
            )

    return Panel(
        table,
        title=f"[bold {color}]{title}[/]",
        border_style=color,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def build_hud(
    title: str,
    title_color: str,
    stats: List[Tuple[str, str, str]],
) -> Panel:
    """Build a crisp top HUD panel with labeled stats."""
    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    for _ in stats:
        grid.add_column(justify="right")

    cells: List[RenderableType] = [Text(f" {title} ", style=f"bold {title_color}")]
    for label, value, color in stats:
        cells.append(
            Text.assemble(
                (f"{label}: ", "dim"),
                (f"{value} ", f"bold {color}"),
            )
        )
    grid.add_row(*cells)

    return Panel(
        grid,
        border_style=title_color,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def build_status_banner(
    headline: str,
    details: str,
    color: str,
    hint: str,
) -> Panel:
    """Build a centered overlay/status panel for pause or game over."""
    body = Group(
        Align.center(Text(headline, style=f"bold {color}")),
        Align.center(Text(details, style="bold white")),
        Align.center(Text(hint, style="dim")),
    )
    return Panel(
        body,
        border_style=color,
        box=box.DOUBLE,
        padding=(0, 3),
    )
