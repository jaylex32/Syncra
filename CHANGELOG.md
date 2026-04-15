# Changelog

## v2.20.5 - 2026-04-14
### 🛠️ Smart Match Cache Stability Hotfix
- Fixed Smart Match cache database handling so broken cache files no longer prevent Syncra from opening on some systems.
- Moved relative Smart Match cache storage into local app data for more reliable binary and server behavior.
- Fixed Smart Match rebuild UI freezes caused by repeated cache-status probing on the main thread.
- Fixed Smart Match rebuild completion flow so the final dialog closes correctly after indexing finishes.
- Improved Smart Match rebuild progress reporting with a clear finalization step instead of appearing stuck at 100%.

## v2.20.3 - 2026-04-12
### 🚀 Smart Match Performance, Spotify Import Recovery, and Editor UX
- Replaced session-only Smart Match indexing with a persistent on-disk cache, including restart reuse, library fingerprint validation, and Settings controls to rebuild or clear the cache.
- Added real Smart Match progress phases and cache-status reporting so large-library indexing no longer appears stuck behind fake placeholder percentages.
- Added a Syncra startup splash screen with live boot progress and Smart Match cache-check visibility for a more professional app launch experience.
- Fixed Smart Match import state handling so playlist creation always uses the completed worker result set and no longer fails with empty-item playlist creation errors.
- Improved Smart Match preload and shutdown behavior with cleaner cancellation and thread cleanup.
- Fixed Spotify playlist import reliability and recovery for environments where track loading was failing.
- Fixed multiple Spotify import failure modes, including broken pagination loops, misleading loading states, and converter-thread integration issues during Plex playlist creation.
- Fixed Apple Music XML temp playlist naming so imported Plex playlists keep the original Apple playlist name instead of leaking random temp-file names.
- Improved Playlist Editor responsiveness while loading by moving heavy metadata preparation off the UI thread and rendering rows incrementally.
- Fixed Playlist Editor drag-and-drop reordering crash under PyQt6.
- Added playlist sorting tools in the editor, including duplicate-friendly sort modes and an `Original Playlist Order` restore option for cleanup workflows.
- Added duplicate highlighting, unsaved-change tracking, and expanded row context actions in Playlist Editor.
- Fixed Playlist Editor cover preview to prefer custom Plex playlist posters instead of always showing Plex-generated default collage art.

## v2.20.2 - 2026-03-09
### 🎯 Smart Matching Reliability + UX
- Reworked **smart M3U matching** for NAS, remote-server, and remapped-path libraries so imports no longer depend on exact case-sensitive path matches.
- Added stronger path parsing and metadata extraction for path-only M3U files, including better handling for portable-backup paths, mixed separators, URL-encoded paths, and artist-prefixed album folders.
- Fixed smart matching false metadata extraction from container folders like `Playlists` / `Rock Hits`, preventing those values from polluting artist/album scoring.
- Improved ambiguous-match scoring so duplicate title/artist tracks prefer the correct album version more consistently.
- Added session-level smart-match library indexing reuse so repeated imports against the same connected Plex library are significantly faster after the first run.
- Replaced status-bar-only smart-match startup feedback with a dedicated **Smart Match Import** progress dialog.
- Added **Cancel Import** support to the smart-match progress dialog with clean worker cancellation.
- Fixed a Qt thread-affinity warning in batched playlist track-count loading by removing nested worker-thread parenting.

## v2.20.1 - 2026-03-03
### 🛠️ Portable Backup + Local Tracks Fixes
- Added a new **Portable Backup** option to preserve Plex server folder hierarchy (relative to the library root), so exported media can keep paths like `Artist/Album/Track.ext`.
- Applied hierarchy-preserving path handling to both local-copy and remote-download backup flows.
- Updated portable M3U placement rules to avoid conflicting layout modes when hierarchy preservation is enabled.
- Fixed **Local Tracks** `Select All` behavior under PyQt6 so it correctly checks every discovered track.
- Fixed Local Tracks rescans to keep new results aligned with the current `Select All` toggle state.

## v2.20.0 - 2026-03-02
### 🚀 Portable Backup + Editor Overhaul + UX Polish
- Added **Portable Backup** as a dedicated Tools dialog to export playlists together with actual audio media files.
- Added remote Plex media download fallback for portable backup when source file paths are not locally accessible.
- Added portable backup options for scope selection, dedupe, manifest output, ZIP packaging, and M3U generation with portable relative paths.
- Added asynchronous playlist loading inside the portable backup dialog to prevent UI freezes with large libraries.
- Added scheduled **Plex Server Sync Jobs** improvements to run from saved source/target server profiles (not only current UI connection).
- Fixed scheduled server job config normalization for target profile and target section metadata.
- Fixed Spotify playlist cover import reliability:
  - Normalized `spotify:image:` and related image URI formats to real CDN URLs.
  - Added fallback cover resolution from Spotify metadata/OpenGraph when Web API image lookup fails.
  - Hardened Plex poster upload fallback path.
- Overhauled **Playlist Editor** with a modern split layout, improved loading state, and stronger visual consistency.
- Added playlist cover preview/change workflow directly in Playlist Editor with external image upload and save-time cover apply.
- Improved playlist editor loading UX with centered loading card, retry action, cleaner transitions, and hidden action bar until ready.
- Themed playlist editor table corner/header visuals to remove mismatched gray corner block artifacts.
- Applied row-level control alignment polish across Streaming Import, Sync Manager, Local Tracks, and Settings mapping controls for consistent button/field centering.

## v2.19.0 - 2026-03-02
### ✅ Matching Accuracy, Ordering, and ListenBrainz Reliability
- Fixed smart matching filters not being applied in worker-thread matching paths (sync/import), which could previously prefer live/acoustic/compilation variants.
- Upgraded source-track normalization to include structured metadata (`title`, `artist`, `album`, optional MBID) across Spotify, Deezer, Tidal, and ListenBrainz import/sync flows.
- Improved confidence scoring with stronger title/artist gating, album-aware weighting, and safer fallback thresholds to reduce unrelated auto-matches.
- Added MusicBrainz recording MBID-aware preference when available (especially from ListenBrainz payloads) to improve deterministic track resolution.
- Fixed playlist sync ordering fidelity: source tracks now preserve source order instead of appending newly matched tracks at the end.
- Refined duplicate handling so de-duplication-by-signature is scoped to M3U path flows and does not incorrectly suppress or mis-route streaming track matches.
- Fixed ListenBrainz playlist list reliability by re-fetching track counts when API responses return missing/placeholder values.
- Added optional ListenBrainz playlist artwork import support by detecting direct image URLs inside playlist annotation/description payloads and applying poster art to Plex playlists on import.
- Improved low-confidence confirmation dialog rendering for structured source-track metadata.

## v2.18.1 - 2026-03-01
### 🛠️ Hotfix
- Fixed packaged app startup crash on Windows release builds:
  - `ModuleNotFoundError: No module named 'syncra.config'`
- Root cause was repository ignore rules excluding `syncra/config`.
- Added package config files (`syncra/config/__init__.py`, `syncra/config/defaults.py`) to source control and adjusted `.gitignore` exceptions.
- Rebuilt and republished binaries with the corrected package contents.

## v2.18.0 - 2026-03-01
### 🎨 UI Refresh and UX Improvements
- Delivered a full modernized dark UI pass with consistent section headers, cards, spacing, and action hierarchy.
- Replaced sidebar/action emoji navigation with packaged icon assets from `assets/icons`.
- Added themed scrollbars and improved visual consistency across pages and dialogs.
- Reskinned the playlist editor dialog to match the new application design language.
- Updated labels and copy polish across key screens (for example `Tools & Utilities`, `Import & Export`).

### 🔐 Plex Auth and User Management
- Added explicit Plex 2FA code input to the Connection flow.
- Implemented token-first reconnect to prevent repeated 2FA prompts on app startup.
- Improved `Switch User` fallback behavior to use token-based account context first, then credential + 2FA fallback only when necessary.
- Fixed PyQt6 enum migration crash in user-switch dialog/window flags and header behaviors.

### 🧠 Streaming and Integrations
- Added ListenBrainz tabbed integration workflow for cleaner import/export controls.
- Fixed ListenBrainz export payload handling to prevent `400 BAD REQUEST` on playlist creation.
- Added progress feedback and non-blocking threading for ListenBrainz operations.
- Fixed ListenBrainz playlist loading issues (untitled names and incorrect track count reporting).

### 🍎 Apple Music XML Import
- Added new `Apple Music XML` tab under Streaming Import.
- Implemented parser for Apple Music/iTunes XML (plist) exports, including static and exported smart-playlist snapshots.
- Added optional Plex rating import mapping from Apple ratings.
- Added **Dry Run Preview** with per-playlist match statistics (`Tracks`, `Matched`, `Missing`, `Match %`, `Rating Candidates`) and missing-track samples before import.
- Reused existing path-mapping system for cross-platform/media-root matching compatibility.

### 🧬 Metadata Workflow Update
- Transitioned metadata tooling to a file-first metadata editing model using local audio tags.
- Updated metadata-related UI labels/tooltips to reflect file-tag behavior and configuration.
- Added `mutagen` dependency for local tag read/write support.

### ⚙️ Packaging and Build
- Completed PyQt6 packaging updates in CI/release workflows, including `PyQt6.QtSvg` and `PyQt6.QtSvgWidgets` hidden imports.
- Added bundled assets in PyInstaller commands so icons/theme resources are included in binaries.
- Updated runtime requirements to `PyQt6>=6.10.2,<6.11`.

## v2.15.0 - 2026-02-28
### 🚀 Modernization Baseline
- Migrated runtime and packaging from **PyQt5** to **PyQt6**.
- Introduced a thin bootstrap `main.py` and moved the legacy application module to `syncra/app/legacy_main.py`.
- Added package structure for staged refactor: `app`, `ui`, `workers`, `services`, `models`, `config`, and `theme`.
- Added centralized theme module (`syncra/theme/styles.py`) and switched main stylesheet loading to shared theme tokens.

### 🧠 Metadata Fixer Foundation
- Added **Metadata Fixer** dialog and workflow scaffold in Tools & Utilities.
- Added MusicBrainz + Cover Art Archive provider with cache and rate limiting.
- Added metadata proposal/apply service with audit logging to `temp/metadata_audit_log.jsonl`.
- Added runtime feature flag `features.metadata_fixer` (disabled by default).

### ⚙️ Config and Logging
- Added config defaults merge logic for app/sync/cache files.
- Added structured logging utilities with flow IDs and timing helpers.
- Added log instrumentation for fetch/sync/import workflows.

### ✅ Tests
- Added smoke harness test (`tests/test_smoke_harness.py`) for critical GUI entrypoint surfaces.
- Added metadata fixer service test (`tests/test_metadata_fixer_service.py`).

## v2.14.0 - 2025-12-31
### 🎯 Critical Fix: Spotify Authentication Overhaul
- **Fixed Spotify API breaking changes from December 22, 2025**
  - Spotify introduced new API restrictions requiring OAuth for track data
  - Implemented hybrid authentication system (cookie TOTP + OAuth Client Credentials)
  - All Spotify playlists now work flawlessly (including algorithmic playlists)

### 🔐 Hybrid Authentication System
- **Cookie-based TOTP Authentication** (for playlist metadata)
  - Generates temporary tokens from user's `sp_dc` cookie
  - Uses `spclient.wg.spotify.com` internal API endpoint
  - Requires `Client-Id` header (critical Dec 22, 2025 change)
  - Prevents 429 rate limit errors on playlist requests

- **OAuth Client Credentials** (for track details)
  - Built-in OAuth app credentials (no user setup required)
  - Fetches individual tracks from `api.spotify.com/v1/tracks`
  - One track at a time with 100ms delays to avoid rate limits
  - Required due to Spotify's new restrictions on track information retrieval

### 🚀 Updated All Spotify API Calls
- **SyncThread.get_spotify_tracks()** - Updated to use spclient + OAuth
- **PlaylistSortingThread.get_spotify_tracks()** - Updated to use spclient + OAuth
- **LoadUserPlaylistsThread** - Updated to use proper TOTP token authentication
- **PlaylistConverterThread.get_spotify_playlist_info()** - Already correct implementation

### 📚 Comprehensive User Documentation
- **SPOTIFY_AUTH_SOLUTION.md** - Technical implementation details
- **SPOTIFY_OAUTH_SETUP_GUIDE.md** - Step-by-step guide for creating personal OAuth app
- **USER_OAUTH_README.md** - User-facing documentation with FAQ
- **SPOTIFY_QUICK_SETUP.txt** - Quick reference card for OAuth setup
- **app_config.json.template** - Configuration template with helpful comments

### ✅ What Users Get
- **Out-of-Box Experience**: Works immediately with built-in OAuth credentials
- **No Configuration Needed**: Users only provide `sp_dc` cookie (from browser)
- **Optional Personal OAuth**: Users can create their own OAuth app for unlimited rate limits
- **Seamless Upgrade**: No breaking changes, existing users continue working

### 🔧 Technical Improvements
- Removed credential exposure from logs and documentation
- OAuth credentials built-in as defaults with environment variable overrides
- Automatic credential storage in `app_config.json` for persistence
- Clean separation between shared and personal OAuth credentials
- Comprehensive authentication testing via `test_spotify_auth.py`

### 📊 User OAuth Benefits (Optional)
- Personal rate limit quota (~180 requests/minute)
- No sharing with other Syncra users
- Guaranteed reliability for heavy usage
- 100% free (Spotify Developer account is free)
- 5-minute setup process

### 🐛 Bug Fixes
- Fixed 429 rate limit errors on Spotify playlist fetching
- Fixed track information retrieval failures
- Fixed algorithmic playlist access issues
- Fixed rate limiting when using cookie authentication

### 🎓 Reference Implementation
Based on approach from: https://github.com/misiektoja/spotify_monitor
- Key learnings: Use `spclient.wg.spotify.com` for playlists, OAuth for tracks
- Fetch tracks individually with delays (not batched)
- Include `Client-Id` header for cookie-based requests

### 📝 Migration Notes
- No action required for existing users
- OAuth credentials automatically added to config on first run
- Old documentation files removed to prevent credential exposure
- Clean upgrade path from v2.13.0

## v2.13.0 - 2025-11-23
### 🎭 Major Features: Multi-User Management System
- **Complete Plex Home User Support**
  - User selection dialog on login with beautiful dark-themed UI
  - Support for Administrator, Home Users, and Friends
  - Per-user playlist management and preferences
  - Switch between users without re-entering credentials
  - User context displayed in window title and status bar
  - User-specific playlists and library access

### 🔐 Production-Ready Security: Multi-OS Credential Storage
- **SecureCredentialManager** - Enterprise-grade credential protection
  - **Windows**: Windows Credential Manager integration (native encrypted storage)
  - **macOS**: Keychain integration (native encrypted storage)
  - **Linux**: Secret Service API (GNOME Keyring/KWallet)
  - **Fallback**: AES-256 encrypted file storage (all platforms)
  - Machine-specific encryption using PBKDF2-HMAC-SHA256 (100,000 iterations)
  - File permissions restricted to owner only (Unix: 0600)
  - Automatic migration from old base64 storage
  - PyInstaller/binary compatible
  - Zero plain-text password storage

### 🚀 Performance: Multi-Threaded M3U Upload
- **SmartM3UUploadThread** - Background M3U processing
  - Prevents UI freezing during large playlist imports
  - Real-time progress updates and status messages
  - User prompts for ambiguous track matches (medium/low confidence)
  - Comprehensive track matching with multiple search strategies
  - Smart scoring algorithm (title: 40pts, artist: 60pts)
  - Auto-skip option for uncertain matches

### 🎯 Enhanced M3U Matching System
- **Dual Matching Modes** for M3U playlists
  - **Smart Matching** (recommended for NAS/remote servers)
    - Metadata-based matching using Plex search API
    - Works across different mount points and file paths
    - Ideal for remote servers and NAS configurations
  - **Path Matching** (for local servers)
    - Exact file path matching with multiple strategies
    - Suffix matching for different mount points
    - Partial matching (last 3+ path components)
  - User-selectable mode with detailed UI descriptions
  - Automatic fallback to fuzzy matching if path matching fails

### 🎨 UI/UX Enhancements
- **User Management UI**
  - 👤 Administrator indicator in user list
  - 🏠 Home User indicator in user list
  - 👥 Friend indicator in user list
  - "Switch User" button on connection page
  - Current user status label with color coding
  - Double-click to select user
  - Helpful tooltips and error messages

- **M3U Matching Mode UI**
  - Radio button selection with clear descriptions
  - Color-coded info panels explaining each mode
  - Warning messages for troubleshooting
  - Visual feedback during track matching

- **Dark Theme Improvements**
  - Fixed white background in track selection scroll areas
  - Consistent dark theme across all dialogs
  - Improved contrast and readability

### 🔧 Technical Improvements
- **Enhanced Duplicate Detection**
  - Uses Plex rating keys for exact duplicate detection
  - Prevents re-adding already present tracks in playlists
  - Works with both path matching and fuzzy matching modes

- **Path-Based Track Finding**
  - Three-tier matching strategy (exact, suffix, partial)
  - Handles different mount points and path separators
  - Cross-platform path normalization
  - Comprehensive logging for debugging

- **Plex Search API Integration**
  - Reliable cross-platform track matching
  - Server-side search for better performance
  - Fuzzy matching with relevance ranking
  - Support for title and artist-based queries

- **Sync System Updates**
  - Preserves both original file paths and parsed metadata
  - Intelligent duplicate detection during sync
  - Support for mixed M3U formats (paths vs. parsed)
  - Improved error handling and recovery

### 🐛 Critical Bug Fixes
- Fixed M3U upload UI freezing during track search
- Fixed home user authentication (401 Unauthorized) errors
- Fixed user switching requiring password re-entry
- Fixed auto-login not preserving user selection
- Fixed scroll area white background in track selection dialog
- Fixed missing import for QButtonGroup and QRadioButton
- Fixed syntax errors from truncated code in previous session

### 🔄 Auto-Login & Session Management
- Automatic reconnection with saved user context
- Seamless user switching without re-authentication
- Admin token saved for home user access
- Smart fallback to admin if saved user not found
- Graceful error handling with helpful messages

### 📊 Scheduled Sync Features
- Date/time picker for scheduling sync operations
- Repeat options: Once, Daily, Weekdays, Weekly, Bi-Weekly, Monthly
- Real-time status display for scheduled syncs
- Automatic sync execution at scheduled times
- Minute-level precision with background timer

### 💾 Configuration Management
- User selection persisted across sessions
- Secure credential storage (not in config file)
- Automatic credential migration on first run
- Path mapping settings preserved
- M3U matching mode preference saved

### 🏗️ Architecture Improvements
- Clean separation of concerns (credential storage, user management, UI)
- Multi-OS compatibility throughout codebase
- Graceful fallback mechanisms at every level
- Comprehensive error handling and logging
- Production-ready code quality

### 📝 Developer Notes
- Added extensive inline documentation
- Clear migration path from v2.12.0
- Backward compatible configuration loading
- No breaking changes for existing users
- Ready for PyInstaller compilation on all platforms

### 🎉 User Experience Wins
- ✅ No password re-entry when switching users
- ✅ No UI freezing during M3U uploads
- ✅ Works with remote Plex servers and NAS
- ✅ Secure credential storage (not in plain text)
- ✅ Beautiful, intuitive user interface
- ✅ Automatic login with last selected user
- ✅ Clear visual feedback throughout the app

## v2.12.0 - 2025-10-21
### Spotify Authentication Updates
- Implemented resilient TOTP-based token refresh with rotating browser user agents.
- Added support for fetching Spotify secret dictionaries from configurable URLs or local files.
- Improved retry logic, backoff timing, and validation to reduce anonymous token failures.

### Developer Experience
- Bumped application version metadata to 2.12.0 for the release packaging.

## v2.11.2 - 2025-09-30
### Critical Bug Fixes
- **Fixed case sensitivity bug in path mapping system** - Path mappings were converting all paths to lowercase, causing Plex to reject uploads with 400/500 errors
- **Fixed missing #EXTM3U header in normalized M3U files** - M3U files now properly include required header for Plex compatibility
- **Fixed path mappings not displaying in Settings UI after restart** - Added missing UI refresh call when loading saved path mappings from config
- Added automatic diagnostic log creation when playlist uploads fail, providing detailed error analysis and troubleshooting information

### Technical Details
- Modified `apply_path_mappings()` to preserve original case while doing case-insensitive prefix matching
- Ensured all file path operations maintain exact case from source files
- Added #EXTM3U header validation and automatic injection during M3U normalization
- Path mappings now correctly display in Settings UI immediately after program restart

## v2.11.1 - 2025-09-30
### Bug Fixes
- Fixed critical path separator mixing issue in path mapping system
- Corrected `apply_path_mappings()` to maintain consistent separators throughout transformed paths
- Issue was causing mixed separators like `F:\Music\Artist/Album/Track.flac` instead of `F:\Music\Artist\Album\Track.flac`
- Now properly uses target path's separator style for entire transformed path

## v2.11.0 - 2025-09-30
### Major Features Added
- **Comprehensive Path Mapping System for M3U Playlist Uploads**
  - Universal path transformation engine supporting all storage configurations
  - Works with Windows, Linux, macOS, Synology NAS, Network Shares, and UNC paths
  - Automatic path detection from Plex API
  - User-configurable path mapping rules with persistent storage
  - Smart path suggestion system based on detected Plex library paths
  - Cross-platform path normalization (Windows ↔ Unix)

### New Settings & UI
- **Path Mappings Configuration Panel in Settings**
  - Visual path mapping manager with add/remove functionality
  - Auto-detect Plex library paths button
  - Quick preset templates:
    - Windows → Synology NAS (C:\ → /volume1/)
    - Windows → Linux/Mac (C:\ → /mnt/)
    - UNC Network → Synology (\\NAS\ → /volume1/)
  - Real-time mapping list display
  - Duplicate detection and replacement prompts

### Enhanced Diagnostics
- **Detailed Upload Diagnostic Logging System**
  - Comprehensive failure analysis for M3U uploads
  - Path type detection (UNC, Windows, Unix, Network)
  - Automatic comparison with Plex library paths
  - Actionable recommendations and suggested mappings
  - Logs saved to upload_logs folder with timestamps
  - First 50 failed tracks detailed with path analysis

### Technical Improvements
- Integrated path mapping application into M3U normalization pipeline
- Path mappings automatically applied to all track paths during upload
- Persistent configuration storage in app_config.json
- Case-insensitive path matching for cross-platform compatibility
- Smart path prefix detection and replacement
- Support for relative and absolute paths

### User Experience
- One-time configuration with automatic transformation on every upload
- No manual intervention needed after initial setup
- Clear visual feedback on applied mappings in logs
- Preset templates for common scenarios reduce configuration time

### Bug Fixes
- Resolved path mismatch issues for users with remote Plex servers
- Fixed cross-platform playlist import failures
- Eliminated need for manual path editing in M3U files

## v2.10.2 - 2025-09-30
### Bug Fixes
- Fixed critical bug where `album_title` variable was not initialized before use in sync manager
- Added proper error handling for album filtering when track metadata is unavailable
- Wrapped filter logic in try-except blocks to prevent crashes during sync operations

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
