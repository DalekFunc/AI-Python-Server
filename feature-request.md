Features
- [x] verify magnet link validity
- [ ] qBittorrent Docker integration
  - Add the `linuxserver/qbittorrent` image via Docker Compose.
  - Provide a helper script that boots both the Python server and qBittorrent stack.
  - Implement communication from the Python server to qBittorrent so that it can verify the container is running and send magnet links for download.
- [ ] On the same server it is hosting a qbittorrent image. send the magnet link to torrent app and start the download.
- [ ] Create a CI/CD pipe line.
