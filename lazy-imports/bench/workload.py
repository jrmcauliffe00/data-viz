"""Import-time load of one real Wikidata extract.

Parsing happens while this module is imported. An eager importer pays that
cost at startup. A lazy importer pays it on first use of a name defined here.
"""

import csv
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "California.csv"


def _load(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    same_state = sum(
        1
        for row in rows
        if row["deathStateLabel"] and row["deathStateLabel"] == row["birthStateLabel"]
    )
    return {
        "file": path.name,
        "rows": len(rows),
        "same_state": same_state,
        "same_state_rate": same_state / len(rows),
    }


SUMMARY = _load(CSV_PATH)
