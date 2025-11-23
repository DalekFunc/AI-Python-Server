Features
- [x] verify magnet link validity
- [x] qBittorrent Docker integration
  - Added the `linuxserver/qbittorrent` image via Docker Compose with health checks and persisted volumes.
  - Provided `scripts/start_stack.sh` to launch both the Flask server and qBittorrent, including readiness verification.
  - Implemented qBittorrent communication inside the Python server so it can verify the container is running, enqueue magnets, and expose job metadata.
- [ ] Youtube Download intergration
  1. The system has installed yt-dlp, a youtube video downloader application. https://github.com/yt-dlp/
  1. The web UI input field now also accepts Youtube URL. 
  1. By parsing the url, it calls system installed yt-dlp application and download content.
  1. Only implement video download at first, audio track can be ignored for now.
  1. Write a simple instructions / guide for user to know what kind of URL/Links are accepted in the webpage input field.
- [ ] Create a CI/CD pipe line.
