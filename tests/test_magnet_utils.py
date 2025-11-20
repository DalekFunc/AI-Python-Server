import base64

from magnet import validate_magnet


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
