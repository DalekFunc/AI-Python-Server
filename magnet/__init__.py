"""Magnet-related helpers for the Magnet Drop service."""

from .utils import (
  MagnetValidationResult,
  ReachabilityProbeResult,
  validate_magnet,
)
from .resolve import (
  MagnetResolutionError,
  ResolvedMagnet,
  extract_magnet_links_from_html,
  is_youtube_url,
  resolve_to_magnet,
)

__all__ = [
  "MagnetResolutionError",
  "ResolvedMagnet",
  "MagnetValidationResult",
  "ReachabilityProbeResult",
  "extract_magnet_links_from_html",
  "is_youtube_url",
  "resolve_to_magnet",
  "validate_magnet",
]
