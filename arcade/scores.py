from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_SCORES_PATH = Path(__file__).resolve().parent.parent / "highscores.json"


@dataclass
class ScoreEntry:
    score: int
    difficulty: str
    detail: str
    date: str


class ScoreStore:
    """Persistent JSON high-score store per game."""

    def __init__(self, path: Optional[Path] = None, max_per_game: int = 5) -> None:
        self.path = path or DEFAULT_SCORES_PATH
        self.max_per_game = max_per_game
        self._data: Dict[str, List[Dict]] = self._load()

    def _load(self) -> Dict[str, List[Dict]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def top_scores(self, game: str) -> List[ScoreEntry]:
        entries = self._data.get(game, [])
        result: List[ScoreEntry] = []
        for item in entries:
            try:
                result.append(
                    ScoreEntry(
                        score=int(item["score"]),
                        difficulty=str(item.get("difficulty", "Normale")),
                        detail=str(item.get("detail", "")),
                        date=str(item.get("date", "")),
                    )
                )
            except (KeyError, ValueError, TypeError):
                continue
        result.sort(key=lambda e: e.score, reverse=True)
        return result[: self.max_per_game]

    def best_score(self, game: str) -> int:
        top = self.top_scores(game)
        return top[0].score if top else 0

    def record(self, game: str, score: int, difficulty: str, detail: str = "") -> bool:
        """Record a score if > 0. Returns True if it is a new #1 record."""
        if score <= 0:
            return False
        previous_best = self.best_score(game)
        entries = self.top_scores(game)
        entries.append(
            ScoreEntry(
                score=score,
                difficulty=difficulty,
                detail=detail,
                date=datetime.now().strftime("%d/%m %H:%M"),
            )
        )
        entries.sort(key=lambda e: e.score, reverse=True)
        trimmed = entries[: self.max_per_game]
        self._data[game] = [asdict(e) for e in trimmed]
        self._save()
        return score > previous_best
