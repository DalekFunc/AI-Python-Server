from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import urlparse

from .utils import validate_magnet


class MagnetResolutionError(ValueError):
  pass


def is_youtube_url(url: str) -> bool:
  parsed = urlparse(url)
  host = (parsed.netloc or "").strip().lower()
  if host.startswith("www."):
    host = host[len("www.") :]
  return host in {"youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com", "youtube-nocookie.com"}


class _HrefCollector(HTMLParser):
  def __init__(self) -> None:
    super().__init__()
    self.hrefs: List[str] = []

  def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
    if tag.lower() != "a":
      return
    for key, value in attrs:
      if key.lower() == "href" and value:
        self.hrefs.append(value)


def extract_magnet_links_from_html(html_text: str) -> List[str]:
  """
  Extract potential magnet links from a HTML document.

  Strategy:
  - Prefer <a href="magnet:?…"> targets
  - Fallback to scanning the whole document for "magnet:?" tokens
  """
  if not html_text:
    return []

  # Unescape HTML entities first so "&amp;" becomes "&" etc.
  unescaped = html.unescape(html_text)

  collector = _HrefCollector()
  try:
    collector.feed(unescaped)
  except Exception:
    # If the HTML is malformed, still try regex fallback below.
    collector.hrefs = collector.hrefs or []

  candidates: List[str] = []
  for href in collector.hrefs:
    href_unescaped = html.unescape(href).strip()
    if href_unescaped.lower().startswith("magnet:?"):
      candidates.append(href_unescaped)

  # Regex fallback: find any inline "magnet:?..." occurrences.
  # Stop at whitespace or common HTML delimiters.
  regex_candidates = re.findall(r"magnet:\\?[^\s\"'<>\\)\\]]+", unescaped, flags=re.IGNORECASE)
  candidates.extend(regex_candidates)

  # Deduplicate while preserving order.
  seen = set()
  deduped: List[str] = []
  for c in candidates:
    if c in seen:
      continue
    seen.add(c)
    deduped.append(c)
  return deduped


@dataclass(frozen=True)
class ResolvedMagnet:
  submitted_value: str
  magnet_link: str
  source_url: Optional[str] = None


def resolve_to_magnet(
  submitted_value: str,
  *,
  fetch_timeout: float = 5.0,
  max_bytes: int = 2_000_000,
  user_agent: str = "MagnetDrop/1.0 (+https://localhost)",
) -> ResolvedMagnet:
  """
  Resolve user input to a validated magnet link.

  Accepted inputs:
  - A magnet link (returned as-is after validation)
  - A non-YouTube http(s) URL pointing at an HTML page that contains a magnet link
  """
  value = (submitted_value or "").strip()
  if not value:
    raise MagnetResolutionError("Empty input.")

  if value.lower().startswith("magnet:?"):
    return ResolvedMagnet(submitted_value=value, magnet_link=value, source_url=None)

  parsed = urlparse(value)
  if parsed.scheme.lower() in {"http", "https"}:
    if is_youtube_url(value):
      raise MagnetResolutionError("YouTube URLs are not supported by this endpoint; paste a magnet link instead.")

    # Fetch the page and attempt to extract a magnet link.
    try:
      import requests
    except ModuleNotFoundError as exc:
      raise MagnetResolutionError("requests is not installed; cannot fetch URLs.") from exc

    try:
      resp = requests.get(
        value,
        timeout=fetch_timeout,
        allow_redirects=True,
        headers={"User-Agent": user_agent},
        stream=True,
      )
      resp.raise_for_status()
      # Cap downloads for safety.
      chunks: List[bytes] = []
      total = 0
      for chunk in resp.iter_content(chunk_size=64 * 1024):
        if not chunk:
          continue
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
          break
      body = b"".join(chunks)
      encoding = resp.encoding or "utf-8"
      html_text = body.decode(encoding, errors="replace")
    except Exception as exc:
      raise MagnetResolutionError(f"Failed to fetch URL: {exc}") from exc

    for candidate in extract_magnet_links_from_html(html_text):
      validation = validate_magnet(candidate)
      if validation.is_valid:
        return ResolvedMagnet(
          submitted_value=value,
          magnet_link=candidate,
          source_url=value,
        )

    raise MagnetResolutionError("No valid magnet link found on the page.")

  raise MagnetResolutionError("Input must be a magnet link or an http(s) URL.")

