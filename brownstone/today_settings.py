"""Validated local Today preferences; atomic persistence, no market data."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class TodaySettings:
    gold_copper: int = 0
    minimum_copper: int = 1000
    mode: str = "scaled"
    percent_basis_points: int = 100
    max_crafts: int = 5
    character: tuple[str, str, str] | None = None

    def __post_init__(self):
        if self.character is not None:
            if (not isinstance(self.character, (tuple, list)) or len(self.character) != 3
                    or any(not isinstance(v, str) or not v for v in self.character)):
                raise ValueError("Character needs name, realm and faction")
            object.__setattr__(self, "character", tuple(self.character))
        integers = (self.gold_copper, self.minimum_copper, self.percent_basis_points, self.max_crafts)
        if any(type(value) is not int or value < 0 for value in integers):
            raise ValueError("Settings must use nonnegative integers")
        if self.mode not in {"fixed", "scaled"} or not 1 <= self.max_crafts <= 1000:
            raise ValueError("Choose fixed or scaled and 1–1000 crafts")
        if self.percent_basis_points > 10000:
            raise ValueError("Percentage must be between 0 and 100")

    @property
    def minimum_gain(self) -> int:
        scaled = (self.gold_copper * self.percent_basis_points + 9999) // 10000
        return max(self.minimum_copper, scaled) if self.mode == "scaled" else self.minimum_copper


def settings_path(data_dir: Path, source_id: str) -> Path:
    """One file per source: the data directory is shared, and each source's funds are its own."""
    return data_dir / f"today-settings.{source_id}.local.json"


def load_settings(path: Path) -> TodaySettings:
    if not path.exists():
        return TodaySettings()
    return TodaySettings(**json.loads(path.read_text(encoding="utf-8")))


def save_settings(path: Path, settings: TodaySettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
