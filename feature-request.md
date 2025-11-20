Features
- [x] verify magnet link validity
- [x] qBittorrent Docker integration
  - Added the `linuxserver/qbittorrent` image via Docker Compose with health checks and persisted volumes.
  - Provided `scripts/start_stack.sh` to launch both the Flask server and qBittorrent, including readiness verification.
  - Implemented qBittorrent communication inside the Python server so it can verify the container is running, enqueue magnets, and expose job metadata.
- [ ] Create a CI/CD pipe line.
