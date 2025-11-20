from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Sequence
from urllib.parse import parse_qs, unquote, urlparse


BTIH_PREFIX = "urn:btih:"
BASE16_PATTERN = re.compile(r"^[a-fA-F0-9]{40}$")
BASE32_PATTERN = re.compile(r"^[A-Z2-7]{32}$")


@dataclass
class MagnetValidationResult:
  is_valid: bool
  errors: list[str]
  xt: str | None = None
  info_hash: str | None = None
  info_hash_encoding: Literal["base16", "base32"] | None = None

  def first_error(self) -> str:
    return self.errors[0] if self.errors else ""


def validate_magnet_link(magnet_link: str) -> MagnetValidationResult:
  errors: list[str] = []

  if not magnet_link:
    errors.append("Empty magnet link.")
    return MagnetValidationResult(False, errors)

  if any(ord(ch) < 32 for ch in magnet_link):
    errors.append("Magnet link contains control characters.")

  if not magnet_link.lower().startswith("magnet:?"):
    errors.append("Magnet link must start with 'magnet:?'.")
    return MagnetValidationResult(False, errors)

  parsed = urlparse(magnet_link)
  if parsed.scheme.lower() != "magnet":
    errors.append("Only magnet links are supported.")
  if parsed.netloc:
    errors.append("Unexpected authority component in magnet link.")

  params = parse_qs(parsed.query)
  xt_values: Sequence[str] = params.get("xt", [])
  if not xt_values:
    errors.append("Missing xt parameter with BTIH info hash.")
    return MagnetValidationResult(False, errors)

  xt_value = _select_btih_target(xt_values)
  if not xt_value:
    errors.append("xt parameter must be a BTIH target (urn:btih:<info hash>).")
    return MagnetValidationResult(False, errors)

  info_hash_validation = _validate_btih_value(xt_value)
  if info_hash_validation:
    info_hash, encoding = info_hash_validation
  else:
    errors.append("BTIH info hash must be 40 hex or 32 Base32 characters.")
    return MagnetValidationResult(False, errors)

  return MagnetValidationResult(
    is_valid=not errors,
    errors=errors,
    xt=xt_value,
    info_hash=info_hash,
    info_hash_encoding=encoding,
  )


def _select_btih_target(values: Sequence[str]) -> str | None:
  for value in values:
    decoded = unquote(value)
    if decoded.lower().startswith(BTIH_PREFIX):
      return decoded
  return None


def _validate_btih_value(xt_value: str) -> tuple[str, Literal["base16", "base32"]] | None:
  hash_part = xt_value[len(BTIH_PREFIX) :]
  if BASE16_PATTERN.fullmatch(hash_part):
    return hash_part.lower(), "base16"

  upper_hash = hash_part.upper()
  if BASE32_PATTERN.fullmatch(upper_hash):
    return upper_hash, "base32"

  return None
