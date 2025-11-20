from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from config import StorageConfig


class JsonlStoreError(RuntimeError):
  """Raised when writing to the JSONL store fails."""


@dataclass
class JsonlStore:
  path: Path
  max_bytes: int
  max_backups: int
  rotation_strategy: str = "rotate"
  index_fields: Sequence[str] = ()

  def __post_init__(self) -> None:
    self.path = Path(self.path)
    self.path.parent.mkdir(parents=True, exist_ok=True)
    self._indexes: Dict[str, Dict[Any, int]] = {field: {} for field in self.index_fields}
    self._loaded_fields: set[str] = set()

  # --------------------------------------------------------------------------- #
  # Public API
  # --------------------------------------------------------------------------- #
  def append(self, payload: Dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False) + "\n"
    encoded_size = len(encoded.encode("utf-8"))
    if encoded_size > self.max_bytes:
      raise JsonlStoreError(
        f"Single log entry exceeds max_bytes ({encoded_size} > {self.max_bytes})."
      )

    self._rotate_if_needed(encoded_size)

    with self.path.open("a", encoding="utf-8") as fp:
      fp.seek(0, os.SEEK_END)
      offset = fp.tell()
      fp.write(encoded)

    for field in self.index_fields:
      value = payload.get(field)
      if value is not None:
        self._indexes.setdefault(field, {})[value] = offset

  def iter_entries(self) -> Iterable[Dict[str, Any]]:
    if not self.path.exists():
      return []
    with self.path.open("r", encoding="utf-8") as fp:
      for line in fp:
        try:
          yield json.loads(line)
        except json.JSONDecodeError:
          continue

  def find_one(self, field: str, value: Any) -> Optional[Dict[str, Any]]:
    if not self.path.exists():
      return None
    if field not in self._loaded_fields:
      self._indexes[field] = self._build_index(field)
      self._loaded_fields.add(field)
    offset = self._indexes.get(field, {}).get(value)
    if offset is None:
      return None
    with self.path.open("r", encoding="utf-8") as fp:
      fp.seek(offset)
      line = fp.readline()
    try:
      return json.loads(line)
    except json.JSONDecodeError:
      return None

  # --------------------------------------------------------------------------- #
  # Internal helpers
  # --------------------------------------------------------------------------- #
  def _build_index(self, field: str) -> Dict[Any, int]:
    index: Dict[Any, int] = {}
    if not self.path.exists():
      return index
    with self.path.open("r", encoding="utf-8") as fp:
      while True:
        offset = fp.tell()
        line = fp.readline()
        if not line:
          break
        try:
          payload = json.loads(line)
        except json.JSONDecodeError:
          continue
        value = payload.get(field)
        if value is not None:
          index[value] = offset
    return index

  def _rotate_if_needed(self, additional_bytes: int) -> None:
    if not self.path.exists():
      return
    current_size = self.path.stat().st_size
    if current_size + additional_bytes <= self.max_bytes:
      return

    if self.rotation_strategy == "truncate":
      self.path.write_text("", encoding="utf-8")
      self._reset_indexes()
      return

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rotated_name = f"{self.path.name}.{timestamp}"
    rotated_path = self.path.with_name(rotated_name)
    self.path.rename(rotated_path)
    self._reset_indexes()

    backups = sorted(
      self.path.parent.glob(f"{self.path.name}.*"),
      key=lambda p: p.stat().st_mtime,
      reverse=True,
    )
    for old_backup in backups[self.max_backups :]:
      try:
        old_backup.unlink()
      except FileNotFoundError:
        continue

  def _reset_indexes(self) -> None:
    self._indexes = {field: {} for field in self.index_fields}
    self._loaded_fields.clear()


class LogStorage:
  """High-level helper that wraps submission and job JSONL stores."""

  def __init__(self, config: StorageConfig) -> None:
    self.submissions = JsonlStore(
      path=config.submission_log_path,
      max_bytes=config.max_bytes,
      max_backups=config.max_backups,
      rotation_strategy=config.rotation_strategy,
    )
    self.jobs = JsonlStore(
      path=config.job_log_path,
      max_bytes=config.max_bytes,
      max_backups=config.max_backups,
      rotation_strategy=config.rotation_strategy,
      index_fields=("job_id",),
    )


__all__ = ["JsonlStore", "JsonlStoreError", "LogStorage"]
