"""Application configuration helpers for Magnet Drop."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _env_flag(name: str, default: str = "0") -> bool:
  return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


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

  qbittorrent: Optional[QbittorrentConfig]
  job_log_path: Path


def load_config() -> AppConfig:
  """Load configuration from environment variables."""

  job_log_path = Path(os.environ.get("TORRENT_JOB_LOG_PATH", "logs/jobs.jsonl"))
  job_log_path.parent.mkdir(parents=True, exist_ok=True)

  qb_enabled = _env_flag("QB_ENABLED", "0") or any(
    os.environ.get(var) for var in ("QB_URL", "QB_USER", "QB_PASS")
  )

  qb_config: Optional[QbittorrentConfig] = None
  if qb_enabled:
    qb_url = os.environ.get("QB_URL", "").strip()
    qb_user = os.environ.get("QB_USER", "").strip()
    qb_pass = os.environ.get("QB_PASS", "").strip()
    qb_category = os.environ.get("QB_CATEGORY", "MagnetDrop").strip() or "MagnetDrop"
    qb_timeout = float(os.environ.get("QB_TIMEOUT", "10.0"))

    missing = [
      name
      for name, value in (("QB_URL", qb_url), ("QB_USER", qb_user), ("QB_PASS", qb_pass))
      if not value
    ]
    if missing:
      missing_envs = ", ".join(missing)
      raise RuntimeError(
        f"qBittorrent integration requested but missing required environment variables: {missing_envs}."
      )

    qb_config = QbittorrentConfig(
      url=qb_url,
      username=qb_user,
      password=qb_pass,
      category=qb_category,
      timeout=qb_timeout,
    )

  return AppConfig(qbittorrent=qb_config, job_log_path=job_log_path)


__all__ = ["AppConfig", "QbittorrentConfig", "load_config"]
