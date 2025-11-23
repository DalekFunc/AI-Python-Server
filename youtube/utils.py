"""YouTube URL validation utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse


@dataclass
class YouTubeValidationResult:
  """Result of YouTube URL validation."""

  url: str
  is_valid: bool
  video_id: str | None = None
  components: Dict[str, Any] = field(default_factory=dict)
  errors: List[str] = field(default_factory=list)

  def to_dict(self) -> Dict[str, Any]:
    return {
      "url": self.url,
      "is_valid": self.is_valid,
      "video_id": self.video_id,
      "components": self.components,
      "errors": self.errors,
    }


# YouTube URL patterns
YOUTUBE_DOMAIN_PATTERNS = [
  r"youtube\.com",
  r"youtu\.be",
  r"m\.youtube\.com",
  r"www\.youtube\.com",
]

# Video ID extraction patterns
VIDEO_ID_PATTERNS = [
  (r"youtube\.com/watch\?.*[&?]v=([a-zA-Z0-9_-]{11})", 1),  # youtube.com/watch?v=...
  (r"youtu\.be/([a-zA-Z0-9_-]{11})", 1),  # youtu.be/...
  (r"youtube\.com/embed/([a-zA-Z0-9_-]{11})", 1),  # youtube.com/embed/...
  (r"youtube\.com/v/([a-zA-Z0-9_-]{11})", 1),  # youtube.com/v/...
]


def validate_youtube_url(url: str) -> YouTubeValidationResult:
  """
  Validate a YouTube URL and extract video ID.

  Supports common YouTube URL formats:
  - youtube.com/watch?v=VIDEO_ID
  - youtu.be/VIDEO_ID
  - youtube.com/embed/VIDEO_ID
  - youtube.com/v/VIDEO_ID
  """
  url = url or ""
  errors: List[str] = []
  components: Dict[str, Any] = {}

  if not url:
    errors.append("YouTube URL cannot be empty.")
    return YouTubeValidationResult(url=url, is_valid=False, components=components, errors=errors)

  url = url.strip()

  # Basic URL structure check
  try:
    parsed = urlparse(url)
  except Exception as exc:
    errors.append(f"Invalid URL format: {exc}")
    return YouTubeValidationResult(url=url, is_valid=False, components=components, errors=errors)

  if not parsed.scheme:
    # Try adding https:// if no scheme
    url = f"https://{url}"
    try:
      parsed = urlparse(url)
    except Exception:
      errors.append("URL must include a scheme (http:// or https://) or be a valid domain.")
      return YouTubeValidationResult(url=url, is_valid=False, components=components, errors=errors)

  if parsed.scheme not in ("http", "https"):
    errors.append(f"URL scheme must be http:// or https://, got: {parsed.scheme}")
    return YouTubeValidationResult(url=url, is_valid=False, components=components, errors=errors)

  # Check if domain matches YouTube patterns
  domain_match = False
  for pattern in YOUTUBE_DOMAIN_PATTERNS:
    if re.search(pattern, parsed.netloc, re.IGNORECASE):
      domain_match = True
      components["domain"] = parsed.netloc
      break

  if not domain_match:
    errors.append(f"URL domain does not appear to be a YouTube domain: {parsed.netloc}")
    return YouTubeValidationResult(url=url, is_valid=False, components=components, errors=errors)

  # Extract video ID
  video_id = None
  full_url = parsed.geturl()

  for pattern, group_idx in VIDEO_ID_PATTERNS:
    match = re.search(pattern, full_url, re.IGNORECASE)
    if match:
      video_id = match.group(group_idx)
      break

  # Fallback: try query parameter for v=
  if not video_id:
    query_params = parse_qs(parsed.query)
    v_params = query_params.get("v", [])
    if v_params:
      candidate_id = v_params[0]
      if re.match(r"^[a-zA-Z0-9_-]{11}$", candidate_id):
        video_id = candidate_id

  if not video_id:
    errors.append("Could not extract video ID from URL. Ensure the URL contains a valid YouTube video ID.")
    return YouTubeValidationResult(url=url, is_valid=False, components=components, errors=errors)

  # Validate video ID format (YouTube video IDs are 11 characters)
  if not re.match(r"^[a-zA-Z0-9_-]{11}$", video_id):
    errors.append(f"Extracted video ID does not match expected format (11 alphanumeric characters): {video_id}")
    return YouTubeValidationResult(url=url, is_valid=False, components=components, errors=errors)

  components["video_id"] = video_id
  components["normalized_url"] = f"https://www.youtube.com/watch?v={video_id}"

  return YouTubeValidationResult(
    url=url,
    is_valid=True,
    video_id=video_id,
    components=components,
    errors=errors,
  )

