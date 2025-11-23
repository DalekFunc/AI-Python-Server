# Stage 4 – YouTube Download Integration

## Goal
Extend the web UI to accept YouTube URLs in addition to magnet links, validate them, and download videos using the system-installed `yt-dlp` application. Provide clear user guidance on accepted URL formats.

## Plan
1. **URL type detection and validation**
   - Create `youtube/utils.py` module with `validate_youtube_url(url: str) -> YouTubeValidationResult` helper.
   - Validate YouTube URL patterns (youtube.com, youtu.be, youtube.com/watch, youtube.com/embed, etc.).
   - Extract video ID and perform basic format checks; optionally probe URL accessibility.
   - Return structured result with `is_valid`, `video_id`, `errors` list, and metadata.

2. **YouTube download client**
   - Create `youtube/client.py` module wrapping `yt-dlp` subprocess calls.
   - Implement `download_video(url: str, output_path: Path, format: str = "bestvideo") -> DownloadResult`.
   - Handle subprocess execution with timeout, capture stdout/stderr for progress/metadata.
   - Support configurable download path via environment variable (e.g., `YT_DOWNLOAD_PATH`).
   - Return job metadata including video title, duration, file path, download status.

3. **Configuration updates**
   - Extend `config.py` with `YouTubeConfig` dataclass (download path, format preference, timeout).
   - Add `YT_ENABLED`, `YT_DOWNLOAD_PATH`, `YT_FORMAT`, `YT_TIMEOUT` environment variables.
   - Document configuration in `README.md`.

4. **Request workflow integration**
   - Update `/submit` endpoint in `app.py` to detect input type (magnet vs YouTube URL).
   - Route to appropriate validation and processing:
     - Magnet links → existing magnet validation → qBittorrent dispatch.
     - YouTube URLs → YouTube validation → yt-dlp download dispatch.
   - Create unified job tracking: log YouTube downloads to same job log with type discriminator.
   - Return 202 Accepted with job identifier for both types.

5. **UI updates**
   - Update HTML template input placeholder to indicate both magnet links and YouTube URLs are accepted.
   - Add user guide section or help text explaining accepted URL formats:
     - YouTube video URLs (youtube.com/watch?v=..., youtu.be/...)
     - Magnet links (magnet:?xt=urn:btih:...)
   - Display appropriate success/error messages for YouTube downloads.

6. **Error handling**
   - Map yt-dlp errors (video unavailable, age-restricted, network issues) to user-friendly API responses.
   - Handle subprocess failures gracefully with retry logic for transient issues.
   - Log download attempts and outcomes to `logs/submissions.jsonl` and `logs/jobs.jsonl`.

7. **Testing**
   - Add unit tests for YouTube URL validation covering various YouTube URL formats.
   - Add unit tests for download client with mocked subprocess calls.
   - Add integration test with a public YouTube video (or mock) to verify end-to-end flow.
   - Test error cases (invalid URLs, unavailable videos, yt-dlp not installed).

8. **Documentation**
   - Update `README.md` with YouTube download feature description.
   - Document required system dependency: `yt-dlp` must be installed and available in PATH.
   - Add example YouTube URLs for testing.
   - Include troubleshooting section for common yt-dlp issues.

## Implementation Notes
- **Video-only focus**: As specified, only download video track initially; audio extraction can be deferred.
- **yt-dlp installation**: Assume `yt-dlp` is pre-installed on the system. Consider adding installation instructions or Docker image updates if needed.
- **Download path**: Store downloads in configurable directory (default: `downloads/youtube/`).
- **Job tracking**: Use same job log format as magnet links but with `type: "youtube"` field for filtering.

## References
- Git stage reference: `stage-4-youtube-download-integration`
- PR checklist anchor: `Stage 4 – YouTube Download Integration`
- yt-dlp documentation: https://github.com/yt-dlp/yt-dlp

