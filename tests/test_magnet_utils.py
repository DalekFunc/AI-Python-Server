import base64

import pytest

from magnet import (
  MagnetResolutionError,
  extract_magnet_links_from_html,
  resolve_to_magnet,
  validate_magnet,
)


def test_validate_magnet_accepts_valid_btih():
  magnet = "magnet:?xt=urn:btih:{hash}&dn=Example&tr=https://tracker.example.com/announce".format(
    hash="A" * 40,
  )

  result = validate_magnet(magnet)

  assert result.is_valid is True
  assert result.errors == []
  assert result.components["info_hash"] == "a" * 40
  assert result.components["trackers"] == ["https://tracker.example.com/announce"]


def test_validate_magnet_requires_xt_parameter():
  result = validate_magnet("magnet:?dn=MissingXt")

  assert result.is_valid is False
  assert "Missing required xt parameter." in result.errors


def test_validate_magnet_rejects_invalid_btih_length():
  result = validate_magnet("magnet:?xt=urn:btih:abc123")

  assert result.is_valid is False
  assert any("info hash" in err.lower() for err in result.errors)


def test_validate_magnet_rejects_whitespace_characters():
  bad_link = "magnet:?xt=urn:btih:{hash} &dn=BadSpace".format(hash="B" * 40)

  result = validate_magnet(bad_link)

  assert result.is_valid is False
  assert any("whitespace" in err.lower() for err in result.errors)


def test_validate_magnet_accepts_base32_btih():
  hex_hash = "0123456789abcdef0123456789abcdef01234567"
  base32_hash = base64.b32encode(bytes.fromhex(hex_hash)).decode("ascii")
  magnet = f"magnet:?xt=urn:btih:{base32_hash}&dn=Base32"

  result = validate_magnet(magnet)

  assert result.is_valid is True
  assert result.components["info_hash"] == hex_hash


def test_validate_magnet_rejects_invalid_base32_btih():
  bogus_base32 = "!" * 32
  result = validate_magnet(f"magnet:?xt=urn:btih:{bogus_base32}")

  assert result.is_valid is False
  assert any("base32" in err.lower() for err in result.errors)


def test_extract_magnet_links_from_html_prefers_href_and_unescapes_ampersands():
  info_hash = "A" * 40
  html_doc = f"""
  <html>
    <body>
      <a href="magnet:?xt=urn:btih:{info_hash}&amp;dn=Example&amp;tr=https://tracker.example/announce">Download</a>
    </body>
  </html>
  """

  magnets = extract_magnet_links_from_html(html_doc)

  assert magnets
  assert magnets[0].startswith("magnet:?xt=urn:btih:")
  assert "&dn=Example" in magnets[0]
  assert "&tr=https://tracker.example/announce" in magnets[0]


def test_resolve_to_magnet_fetches_page_and_picks_first_valid_magnet(monkeypatch):
  info_hash = "B" * 40
  invalid = "magnet:?dn=missing_xt"
  valid = f"magnet:?xt=urn:btih:{info_hash}&dn=Ok"
  html_doc = f'<a href="{invalid}">bad</a><a href="{valid}">good</a>'

  class StubResponse:
    def __init__(self, body: bytes):
      self._body = body
      self.status_code = 200
      self.encoding = "utf-8"

    def raise_for_status(self):
      return None

    def iter_content(self, chunk_size: int = 65536):
      yield self._body

  def stub_get(*args, **kwargs):
    return StubResponse(html_doc.encode("utf-8"))

  import requests

  monkeypatch.setattr(requests, "get", stub_get)

  resolved = resolve_to_magnet("https://example.com/torrent")
  assert resolved.source_url == "https://example.com/torrent"
  assert resolved.magnet_link == valid


def test_resolve_to_magnet_rejects_youtube_urls():
  with pytest.raises(MagnetResolutionError):
    resolve_to_magnet("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
