"""qBittorrent WebUI client helpers."""

from .client import (
  AuthenticationError,
  QbittorrentClient,
  QbittorrentError,
  TorrentDuplicateError,
  TorrentRejectedError,
  TorrentServerUnavailable,
)

__all__ = [
  "AuthenticationError",
  "QbittorrentClient",
  "QbittorrentError",
  "TorrentDuplicateError",
  "TorrentRejectedError",
  "TorrentServerUnavailable",
]
