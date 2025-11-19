from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

BTIH_PREFIX = "urn:btih:"
BTIH_HEX_LENGTH = 40


@dataclass
class ReachabilityProbeResult:
  enabled: bool
  succeeded: Optional[bool]
  reason: str
  tracker_url: Optional[str] = None
  elapsed_ms: Optional[float] = None

  def to_dict(self) -> Dict[str, Any]:
    return {
      "enabled": self.enabled,
      "succeeded": self.succeeded,
      "reason": self.reason,
      "tracker_url": self.tracker_url,
      "elapsed_ms": self.elapsed_ms,
    }


@dataclass
class MagnetValidationResult:
  magnet: str
  is_valid: bool
  components: Dict[str, Any] = field(default_factory=dict)
  errors: List[str] = field(default_factory=list)
  reachability: Optional[ReachabilityProbeResult] = None

  def to_dict(self) -> Dict[str, Any]:
    payload = {
      "magnet": self.magnet,
      "is_valid": self.is_valid,
      "components": self.components,
      "errors": self.errors,
    }
    if self.reachability:
      payload["reachability"] = self.reachability.to_dict()
    return payload


def validate_magnet(
  magnet: str,
  *,
  probe_reachability: bool = False,
  probe_timeout: float = 2.0,
) -> MagnetValidationResult:
  magnet = magnet or ""
  errors: List[str] = []
  components: Dict[str, Any] = {}

  if not magnet:
    errors.append("Magnet link cannot be empty.")
    reachability = _reachability_placeholder(probe_reachability, "Skipped because magnet was empty.")
    return MagnetValidationResult(magnet=magnet, is_valid=False, components=components, errors=errors, reachability=reachability)

  if any(ch.isspace() for ch in magnet):
    errors.append("Magnet link cannot contain whitespace characters; encode spaces as %20.")

  if any(ord(ch) < 32 for ch in magnet):
    errors.append("Magnet link contains control characters which are not allowed.")

  try:
    magnet.encode("ascii")
  except UnicodeEncodeError:
    errors.append("Magnet link must be ASCII; percent-encode non-ASCII characters.")

  parsed = urlparse(magnet)
  if parsed.scheme.lower() != "magnet" or not parsed.query:
    errors.append("Magnet link must start with 'magnet:?'.")

  params = parse_qs(parsed.query, keep_blank_values=True)

  xt_values = params.get("xt", [])
  if not xt_values or not xt_values[0]:
    errors.append("Missing required xt parameter.")
  else:
    xt_value = xt_values[0]
    if not xt_value.lower().startswith(BTIH_PREFIX):
      errors.append("xt parameter must start with 'urn:btih:'.")
    else:
      info_hash = xt_value[len(BTIH_PREFIX) :]
      if len(info_hash) != BTIH_HEX_LENGTH or not _is_hex(info_hash):
        errors.append("BTIH info hash must be 40 hexadecimal characters.")
      else:
        components["info_hash"] = info_hash.lower()

  display_name = params.get("dn", [None])[0]
  if display_name:
    components["display_name"] = display_name

  trackers = params.get("tr", [])
  if trackers:
    components["trackers"] = trackers
  else:
    components["trackers"] = []

  if errors:
    reachability = _reachability_placeholder(
      probe_reachability,
      "Skipped because magnet failed validation." if probe_reachability else "Probe disabled via configuration.",
    )
    return MagnetValidationResult(magnet=magnet, is_valid=False, components=components, errors=errors, reachability=reachability)

  reachability = (
    _probe_reachability(trackers, probe_timeout)
    if probe_reachability
    else _reachability_placeholder(False, "Probe disabled via configuration.")
  )

  return MagnetValidationResult(
    magnet=magnet,
    is_valid=True,
    components=components,
    errors=errors,
    reachability=reachability,
  )


def _is_hex(value: str) -> bool:
  try:
    int(value, 16)
    return True
  except ValueError:
    return False


def _reachability_placeholder(enabled: bool, reason: str) -> ReachabilityProbeResult:
  return ReachabilityProbeResult(
    enabled=enabled,
    succeeded=None,
    reason=reason,
  )


def _probe_reachability(trackers: List[str], timeout: float) -> ReachabilityProbeResult:
  if not trackers:
    return ReachabilityProbeResult(
      enabled=True,
      succeeded=None,
      reason="No trackers were provided to probe.",
    )

  tracker = next(
    (tr for tr in trackers if tr.lower().startswith(("http://", "https://"))),
    None,
  )
  if not tracker:
    return ReachabilityProbeResult(
      enabled=True,
      succeeded=None,
      reason="No HTTP(S) trackers available for reachability probe.",
    )

  start = perf_counter()
  try:
    import requests
  except ModuleNotFoundError:
    return ReachabilityProbeResult(
      enabled=True,
      succeeded=None,
      reason="requests is not installed; cannot perform reachability probe.",
      tracker_url=tracker,
    )

  try:
    response = requests.head(tracker, timeout=timeout, allow_redirects=True)
    succeeded = 200 <= response.status_code < 400
    reason = f"Tracker responded with status {response.status_code}."
  except requests.RequestException as exc:  # type: ignore[attr-defined]
    succeeded = False
    reason = f"Tracker request failed: {exc}"

  elapsed_ms = round((perf_counter() - start) * 1000, 2)
  return ReachabilityProbeResult(
    enabled=True,
    succeeded=succeeded,
    reason=reason,
    tracker_url=tracker,
    elapsed_ms=elapsed_ms,
  )
