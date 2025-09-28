# Changelog

## 2025-09-28
### Added
- Clear-on-sync toggle in the Sync Manager with full persistence and Plex clearing behaviour before reimporting.
- Dedicated `PlaylistTrackTable` that keeps track metadata intact while supporting drag-and-drop reordering.

### Changed
- Streaming import layout now lives in its own group with progress, cancel, and status wiring for consistent feedback.
- Playlist import now normalizes Windows-style paths before uploading to Plex to avoid 500 errors.
- Application startup restores saved Plex settings via `load_config`, including library selection and auto-connect when possible.
- Sync worker and matching routines honour cancellation requests using the new `SyncCancelled` guard.

### Fixed
- Dragging playlist entries no longer leaves empty rows or rescans unnecessarily; selections update inline.
- Clear-search button alignment in the playlist editor for a cleaner toolbar.
- Streaming import feedback cleans up correctly after completion or cancellation.