# Changelog

## v2.10.1 - 2025-09-29
### Bug Fixes
- Fixed critical bug where `best_score` variable was accessed before assignment in playlist conversion
- Fixed same `best_score` initialization issue in sync manager's track matching function
- Both fixes prevent "cannot access local variable 'best_score' where it is not associated with a value" errors during Deezer playlist conversion and sync operations

## v2.10 - 2025-09-29
### Major Features Added
- Complete overhaul of duplicate finder: Now scans entire music library instead of just playlists
- Professional duplicate management UI with comprehensive track details and safe deletion
- Auto-selection of best quality tracks with smart quality scoring
- Optional playlist checking for performance optimization
- Comprehensive logging system for all duplicate operations
- Integrated playlist replacement when deleting tracks used in playlists

### Performance Improvements
- Library-wide scanning with normalized track signatures for accurate duplicate detection
- Optional playlist checking mode for faster scans when playlist info not needed
- Efficient track grouping and quality-based sorting algorithms

### UI/UX Enhancements
- New dedicated Settings tab with global track matching filters
- Professional duplicate management dialog with detailed track information
- Fixed gray text visibility issues in filter options
- Comprehensive progress tracking during long library scans
- Auto-selection functionality for safe duplicate removal

### Technical Improvements
- Enhanced track matching with advanced filtering options (live, compilation, remaster, deluxe)
- Improved UNC path handling with proper case sensitivity for network shares
- Better temp folder management for playlist processing
- Advanced track signature normalization for duplicate detection

### Critical Bug Fixes
- Fixed QProgressDialog import crash during duplicate deletion operations
- Fixed playlist renaming functionality for conflicting playlist names
- Resolved case sensitivity issues with UNC server names
- Fixed track matching filter penalties not being applied correctly

### Data Safety Features
- Comprehensive confirmation dialogs before any deletion operations
- Detailed logging of all duplicate management activities
- Safe playlist integration with track replacement
- No accidental deletion of tracks used in playlists without user confirmation

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