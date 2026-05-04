"""Minimal sequential game-state helpers for session play-calling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GameState:
    """Track a simple offensive game state for sequential play-calling."""

    down: int
    distance: int
    field_position: int
    status: str = "active"

    def apply_gain(self, gain: int) -> "GameState":
        """Apply a gain/loss and update down, distance, field position, and status."""
        if self.status != "active":
            return self

        current_distance = self.distance
        self.field_position = max(0, min(100, self.field_position + gain))

        if self.field_position >= 100:
            self.field_position = 100
            self.status = "touchdown"
            return self

        if gain >= current_distance:
            self.down = 1
            self.distance = 10
            return self

        self.down += 1
        self.distance = current_distance - gain
        if self.down > 4:
            self.status = "turnover_on_downs"
        return self

    def field_zone(self) -> str:
        """Map the field coordinate to the engine field-zone taxonomy."""
        if self.field_position <= 40:
            return "own_territory"
        if self.field_position <= 60:
            return "midfield"
        if self.field_position <= 80:
            return "opp_territory"
        if self.field_position <= 95:
            return "redzone"
        return "goal_line"

    def display_yardline(self) -> str:
        """Render a human-readable yard-line label."""
        if self.field_position == 50:
            return "midfield"
        if self.field_position < 50:
            return f"own {self.field_position}"
        return f"opp {100 - self.field_position}"

    def display_down_distance(self) -> str:
        """Render the standard down-and-distance string."""
        ordinal = {
            1: "1st",
            2: "2nd",
            3: "3rd",
            4: "4th",
        }.get(self.down, f"{self.down}th")
        return f"{ordinal} & {self.distance}"
