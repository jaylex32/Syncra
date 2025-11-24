# Changelog

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