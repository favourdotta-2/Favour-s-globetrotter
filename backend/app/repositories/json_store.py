import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from fastapi import Depends
from filelock import FileLock, Timeout

from app.core.config import Settings, get_settings

Record = dict[str, Any]
Result = TypeVar("Result")


class StorageError(RuntimeError):
    """A persistence error that must not be treated as an empty database."""


class JsonStore:
    def __init__(self, data_dir: Path, catalog_path: Path | None = None) -> None:
        self.data_dir = data_dir
        self.catalog_path = catalog_path or data_dir / "destinations.json"

    def _path(self, collection: str) -> Path:
        if collection == "destinations":
            return self.catalog_path
        if collection not in {
            "users", "itineraries", "chat_messages", "chat_media", "reviews", "app_ratings"
        }:
            raise ValueError("Unknown collection")
        return self.data_dir / f"{collection}.json"

    def _read(self, path: Path, *, required: bool = False) -> list[Record]:
        if not path.exists() and not required:
            return []
        records = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise StorageError(f"Expected an array of objects in {path.name}")
        return records

    def read(self, collection: str) -> list[Record]:
        path = self._path(collection)
        try:
            if collection == "destinations":
                return self._read(path, required=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            with FileLock(str(path) + ".lock", timeout=10):
                return self._read(path)
        except (OSError, UnicodeError, json.JSONDecodeError, Timeout) as exc:
            raise StorageError(f"Cannot read {path.name}") from exc

    def mutate(self, collection: str, operation: Callable[[list[Record]], Result]) -> Result:
        if collection == "destinations":
            raise ValueError("The destination catalogue is read-only")
        path = self._path(collection)
        temporary_path: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Lock the entire transaction across threads and local processes.
            with FileLock(str(path) + ".lock", timeout=10):
                records = self._read(path)
                result = operation(records)
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
                ) as temporary:
                    temporary_path = Path(temporary.name)
                    json.dump(records, temporary, indent=2, ensure_ascii=True)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                os.replace(temporary_path, path)
                temporary_path = None
                return result
        except (OSError, UnicodeError, json.JSONDecodeError, Timeout) as exc:
            raise StorageError(f"Cannot update {path.name}") from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def append(self, collection: str, record: Record) -> Record:
        def insert(records: list[Record]) -> Record:
            records.append(record)
            return record

        return self.mutate(collection, insert)

    def find_one(self, collection: str, key: str, value: Any) -> Record | None:
        return next((record for record in self.read(collection) if record.get(key) == value), None)


def get_store(settings: Settings = Depends(get_settings)) -> JsonStore:
    return JsonStore(settings.data_dir, settings.catalog_path)
