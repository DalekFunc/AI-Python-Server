"""Application configuration helpers for Magnet Drop."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


class ConfigError(RuntimeError):
  """Raised when environment inputs cannot be validated."""


def _env_flag(name: str, default: str = "0") -> bool:
  return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float, *, min_value: float | None = None) -> float:
  raw = os.environ.get(name)
  if raw is None:
    return default
  try:
    value = float(raw)
  except ValueError as exc:
    raise ConfigError(f"{name} must be a number, got {raw!r}.") from exc
  if min_value is not None and value < min_value:
    raise ConfigError(f"{name} must be at least {min_value}, got {value}.")
  return value


def _env_int(name: str, default: int, *, min_value: int | None = None) -> int:
  raw = os.environ.get(name)
  if raw is None:
    value = default
  else:
    try:
      value = int(raw)
    except ValueError as exc:
      raise ConfigError(f"{name} must be an integer, got {raw!r}.") from exc
  if min_value is not None and value < min_value:
    raise ConfigError(f"{name} must be at least {min_value}, got {value}.")
  return value


@dataclass(frozen=True)
class MagnetProbeConfig:
  enabled: bool
  timeout: float


@dataclass(frozen=True)
class StorageConfig:
  submission_log_path: Path
  job_log_path: Path
  max_bytes: int
  max_backups: int
  rotation_strategy: Literal["rotate", "truncate"]


@dataclass(frozen=True)
class RetryPolicy:
  attempts: int
  initial_delay: float
  backoff_factor: float


@dataclass(frozen=True)
class QbittorrentConfig:
  """Configuration required to talk to the qBittorrent WebUI."""

  url: str
  username: str
  password: str
  category: str
  timeout: float = 10.0


@dataclass(frozen=True)
class AppConfig:
  """Top-level configuration for the Flask application."""

  secret_key: str
  magnet_probe: MagnetProbeConfig
  storage: StorageConfig
  qbittorrent: Optional[QbittorrentConfig]
  qbittorrent_retry: RetryPolicy


def load_config() -> AppConfig:
  """Load configuration from environment variables."""

  storage = _build_storage_config()
  magnet_probe = MagnetProbeConfig(
    enabled=_env_flag("MAGNET_REACHABILITY_PROBE", "0"),
    timeout=_env_float("MAGNET_REACHABILITY_TIMEOUT", 2.0, min_value=0.1),
  )
  secret_key = os.environ.get("APP_SECRET_KEY", "dev-secret-key")
  qbittorrent = _build_qbittorrent_config()
  qb_retry = _build_retry_policy()
  return AppConfig(
    secret_key=secret_key,
    magnet_probe=magnet_probe,
    storage=storage,
    qbittorrent=qbittorrent,
    qbittorrent_retry=qb_retry,
  )


def _build_storage_config() -> StorageConfig:
  submissions = Path(os.environ.get("SUBMISSION_LOG_PATH", "logs/submissions.jsonl"))
  jobs = Path(os.environ.get("TORRENT_JOB_LOG_PATH", "logs/jobs.jsonl"))
  for path in (submissions, jobs):
    path.parent.mkdir(parents=True, exist_ok=True)

  max_mb = _env_float("LOG_MAX_MB", 5.0, min_value=0.1)
  max_bytes = int(max_mb * 1024 * 1024)
  max_backups = _env_int("LOG_MAX_BACKUPS", 3, min_value=1)
  strategy = os.environ.get("LOG_ROTATION_STRATEGY", "rotate").strip().lower()
  if strategy not in {"rotate", "truncate"}:
    raise ConfigError("LOG_ROTATION_STRATEGY must be either 'rotate' or 'truncate'.")

  return StorageConfig(
    submission_log_path=submissions,
    job_log_path=jobs,
    max_bytes=max_bytes,
    max_backups=max_backups,
    rotation_strategy="truncate" if strategy == "truncate" else "rotate",
  )


def _build_qbittorrent_config() -> Optional[QbittorrentConfig]:
  qb_enabled = _env_flag("QB_ENABLED", "0") or any(
    os.environ.get(var) for var in ("QB_URL", "QB_USER", "QB_PASS")
  )
  if not qb_enabled:
    return None

  qb_url = os.environ.get("QB_URL", "").strip()
  qb_user = os.environ.get("QB_USER", "").strip()
  qb_pass = os.environ.get("QB_PASS", "").strip()
  qb_category = os.environ.get("QB_CATEGORY", "MagnetDrop").strip() or "MagnetDrop"
  qb_timeout = _env_float("QB_TIMEOUT", 10.0, min_value=0.1)

  missing = [
    name
    for name, value in (("QB_URL", qb_url), ("QB_USER", qb_user), ("QB_PASS", qb_pass))
    if not value
  ]
  if missing:
    missing_envs = ", ".join(missing)
    raise ConfigError(
      "qBittorrent integration requested but missing required environment variables: "
      f"{missing_envs}."
    )

  return QbittorrentConfig(
    url=qb_url,
    username=qb_user,
    password=qb_pass,
    category=qb_category,
    timeout=qb_timeout,
  )


def _build_retry_policy() -> RetryPolicy:
  attempts = _env_int("QB_RETRY_ATTEMPTS", 3, min_value=1)
  initial_delay = _env_float("QB_RETRY_BACKOFF_INITIAL", 0.25, min_value=0.0)
  backoff_factor = _env_float("QB_RETRY_BACKOFF_FACTOR", 2.0, min_value=1.0)
  return RetryPolicy(
    attempts=attempts,
    initial_delay=initial_delay,
    backoff_factor=backoff_factor,
  )


__all__ = [
  "AppConfig",
  "ConfigError",
  "MagnetProbeConfig",
  "QbittorrentConfig",
  "RetryPolicy",
  "StorageConfig",
  "load_config",
]
