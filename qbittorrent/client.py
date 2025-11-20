"""Lightweight qBittorrent WebUI API client."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests

LOG = logging.getLogger(__name__)


class QbittorrentError(RuntimeError):
  """Base error for qBittorrent communication problems."""


class AuthenticationError(QbittorrentError):
  """Raised when authentication fails or the session expires."""


class TorrentServerUnavailable(QbittorrentError):
  """Raised when the qBittorrent server cannot be reached."""


class TorrentRejectedError(QbittorrentError):
  """Raised when qBittorrent rejects a magnet link for any reason."""


class TorrentDuplicateError(TorrentRejectedError):
  """Raised when attempting to enqueue a torrent that already exists."""


class QbittorrentClient:
  """Minimal wrapper around qBittorrent's WebUI HTTP API."""

  def __init__(
    self,
    base_url: str,
    username: str,
    password: str,
    *,
    category: str,
    timeout: float = 10.0,
    session: Optional[requests.Session] = None,
  ) -> None:
    self.base_url = base_url.rstrip("/")
    self.username = username
    self.password = password
    self.category = category
    self.timeout = timeout
    self._session = session or requests.Session()
    self._authenticated = False

  # ---------------------------------------------------------------------------
  # Public helpers
  # ---------------------------------------------------------------------------
  def login(self) -> None:
    """Authenticate against qBittorrent and persist the session cookie."""
    try:
      response = self._session.post(
        self._url("/api/v2/auth/login"),
        data={"username": self.username, "password": self.password},
        timeout=self.timeout,
      )
    except requests.RequestException as exc:
      raise TorrentServerUnavailable(f"Failed to reach qBittorrent: {exc}") from exc

    if response.status_code != 200:
      raise AuthenticationError(
        f"qBittorrent login failed with status {response.status_code}: {response.text.strip()}"
      )

    if response.text.strip().lower() != "ok.":
      raise AuthenticationError(f"Unexpected login response: {response.text.strip()}")

    self._authenticated = True
    LOG.debug("Authenticated with qBittorrent WebUI.")

  def ensure_session(self) -> None:
    if not self._authenticated:
      self.login()

  def health_check(self) -> str:
    """Return qBittorrent version string if the server is reachable."""
    try:
      response = self._request("get", "/api/v2/app/version")
      return response.text.strip()
    except AuthenticationError:
      self.login()
      response = self._request("get", "/api/v2/app/version")
      return response.text.strip()

  def add_magnet(self, magnet_link: str, *, category: Optional[str] = None) -> None:
    """Enqueue a magnet link for download."""
    payload = {
      "urls": magnet_link,
      "category": category or self.category,
      "autoTMM": "false",
      "paused": "false",
    }
    response = self._authed_request("post", "/api/v2/torrents/add", data=payload)
    result = response.text.strip().lower()
    if result.startswith("ok"):
      return
    if "duplicate" in result:
      raise TorrentDuplicateError("Magnet link already exists in qBittorrent.")
    raise TorrentRejectedError(response.text.strip() or "qBittorrent rejected the magnet link.")

  def torrent_info(self, info_hash: str) -> Optional[Dict[str, Any]]:
    """Fetch torrent metadata by hash (if available)."""
    response = self._authed_request("get", "/api/v2/torrents/info", params={"hashes": info_hash})
    try:
      data = response.json()
    except ValueError as exc:
      raise TorrentServerUnavailable(f"Invalid JSON from qBittorrent: {exc}") from exc
    if not data:
      return None
    if isinstance(data, list):
      return data[0]
    return data

  # ---------------------------------------------------------------------------
  # Internal helpers
  # ---------------------------------------------------------------------------
  def _authed_request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
    try:
      self.ensure_session()
      return self._request(method, path, **kwargs)
    except AuthenticationError:
      # Session might have expired; retry once.
      self.login()
      return self._request(method, path, **kwargs)

  def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("timeout", self.timeout)
    try:
      response = self._session.request(method, self._url(path), **kwargs)
    except requests.RequestException as exc:
      raise TorrentServerUnavailable(f"qBittorrent request failed: {exc}") from exc

    if response.status_code == 403:
      self._authenticated = False
      raise AuthenticationError("qBittorrent session expired or invalid credentials.")

    if response.status_code >= 500:
      raise TorrentServerUnavailable(
        f"qBittorrent server error ({response.status_code}): {response.text.strip()}"
      )

    if response.status_code >= 400:
      raise TorrentRejectedError(
        f"qBittorrent returned {response.status_code}: {response.text.strip()}"
      )

    return response

  def _url(self, path: str) -> str:
    base = f"{self.base_url}/"
    return urljoin(base, path.lstrip("/"))


__all__ = [
  "AuthenticationError",
  "QbittorrentClient",
  "QbittorrentError",
  "TorrentDuplicateError",
  "TorrentRejectedError",
  "TorrentServerUnavailable",
]
