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
class YouTubeConfig:
  """Configuration for YouTube download integration."""

  download_path: Path
  format: str = "bestvideo"
  timeout: float = 300.0
  ytdlp_command: str = "yt-dlp"


@dataclass(frozen=True)
class AppConfig:
  """Top-level configuration for the Flask application."""

  qbittorrent: Optional[QbittorrentConfig]
  youtube: Optional[YouTubeConfig]
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

  # YouTube download configuration
  yt_enabled = _env_flag("YT_ENABLED", "1")  # Enabled by default
  yt_config: Optional[YouTubeConfig] = None
  if yt_enabled:
    yt_download_path = Path(os.environ.get("YT_DOWNLOAD_PATH", "downloads/youtube"))
    yt_download_path.mkdir(parents=True, exist_ok=True)
    yt_format = os.environ.get("YT_FORMAT", "bestvideo").strip() or "bestvideo"
    yt_timeout = float(os.environ.get("YT_TIMEOUT", "300.0"))
    yt_ytdlp_command = os.environ.get("YT_YTDLP_COMMAND", "yt-dlp").strip() or "yt-dlp"

    yt_config = YouTubeConfig(
      download_path=yt_download_path,
      format=yt_format,
      timeout=yt_timeout,
      ytdlp_command=yt_ytdlp_command,
    )

  return AppConfig(qbittorrent=qb_config, youtube=yt_config, job_log_path=job_log_path)


__all__ = ["AppConfig", "QbittorrentConfig", "YouTubeConfig", "load_config"]
