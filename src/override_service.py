#=================================================
# IMPORTS
#=================================================
import json
import os

from models import Category
from typing import NotRequired, TypedDict


#=================================================
# CLASSES
#=================================================
class TxOverride(TypedDict):
    category: str
    note: str
    # set during processing; not stored in the JSON file
    match_found: NotRequired[bool]


class OverrideRepository:
    def __init__(self, path: str):
        self._path = path

    def load(self) -> dict[str, TxOverride]:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                overrides = json.load(f) or {}

                # initialize runtime-only fields
                for override in overrides.values():
                    override["match_found"] = False

                return overrides

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Invalid override file: {e}")
            return {}

    def save(self, overrides: dict[str, TxOverride]) -> None:
        tmp_path = self._path + ".tmp"

        data = {}

        # iterate over overrides
        for key, override in overrides.items():
            data[key] = {}
            # iterate over fields
            for field, value in override.items():
                # skip runtime-only field
                if field != "match_found":
                    data[key][field] = value

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        os.replace(tmp_path, self._path)

class TxCategoryOverrideService:
    def __init__(self, repo: OverrideRepository):
        self._repo = repo
        self._overrides: dict[str, TxOverride] = repo.load()

    def is_overridden(self, tx_id: str) -> bool:
        """Check if a transaction has a manual category override."""
        return tx_id in self._overrides

    def all_found(self) -> bool:
        """Check if every stored override matched a transaction."""
        return all(
            override.get("match_found", False)
            for override in self._overrides.values()
        )

    def missing_overrides(self) -> list[str]:
        return [
            tx_id
            for tx_id, override in self._overrides.items()
            if not override.get("match_found", False)
        ]

    def get(self, tx_id: str, base_category: Category) -> tuple[Category, bool, str]:
        """Return overridden category if exists, otherwise fallback to base category."""
        override = self._overrides.get(tx_id)
        if override is None:
            return base_category, False, ""

        # mark runtime-only match
        override["match_found"] = True
        return Category(override["category"]), True, override["note"]

    def set(self, tx_id: str, category: Category, note: str) -> None:
        """Store or update category override for a transaction and persist it."""
        self._overrides[tx_id] = {
            "category": category.value,
            "note": note,
        }
        self._repo.save(self._overrides)
