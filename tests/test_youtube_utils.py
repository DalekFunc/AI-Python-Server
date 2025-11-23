"""Tests for YouTube URL validation."""

from youtube import validate_youtube_url


def test_validate_youtube_url_accepts_standard_watch_url():
  url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  result = validate_youtube_url(url)

  assert result.is_valid is True
  assert result.video_id == "dQw4w9WgXcQ"
  assert result.errors == []


def test_validate_youtube_url_accepts_youtu_be_short_url():
  url = "https://youtu.be/dQw4w9WgXcQ"
  result = validate_youtube_url(url)

  assert result.is_valid is True
  assert result.video_id == "dQw4w9WgXcQ"
  assert result.errors == []


def test_validate_youtube_url_accepts_embed_url():
  url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
  result = validate_youtube_url(url)

  assert result.is_valid is True
  assert result.video_id == "dQw4w9WgXcQ"
  assert result.errors == []


def test_validate_youtube_url_accepts_url_without_scheme():
  url = "youtube.com/watch?v=dQw4w9WgXcQ"
  result = validate_youtube_url(url)

  assert result.is_valid is True
  assert result.video_id == "dQw4w9WgXcQ"


def test_validate_youtube_url_accepts_mobile_url():
  url = "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
  result = validate_youtube_url(url)

  assert result.is_valid is True
  assert result.video_id == "dQw4w9WgXcQ"


def test_validate_youtube_url_rejects_empty_url():
  result = validate_youtube_url("")

  assert result.is_valid is False
  assert "cannot be empty" in result.errors[0].lower()


def test_validate_youtube_url_rejects_non_youtube_domain():
  url = "https://example.com/watch?v=dQw4w9WgXcQ"
  result = validate_youtube_url(url)

  assert result.is_valid is False
  assert any("youtube" in err.lower() for err in result.errors)


def test_validate_youtube_url_rejects_url_without_video_id():
  url = "https://www.youtube.com/watch"
  result = validate_youtube_url(url)

  assert result.is_valid is False
  assert any("video id" in err.lower() for err in result.errors)


def test_validate_youtube_url_rejects_invalid_video_id_format():
  url = "https://www.youtube.com/watch?v=short"
  result = validate_youtube_url(url)

  assert result.is_valid is False
  assert any("format" in err.lower() or "video id" in err.lower() for err in result.errors)


def test_validate_youtube_url_handles_url_with_extra_parameters():
  url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxxx&index=1"
  result = validate_youtube_url(url)

  assert result.is_valid is True
  assert result.video_id == "dQw4w9WgXcQ"


def test_validate_youtube_url_rejects_invalid_scheme():
  url = "ftp://www.youtube.com/watch?v=dQw4w9WgXcQ"
  result = validate_youtube_url(url)

  assert result.is_valid is False
  assert any("scheme" in err.lower() for err in result.errors)

