<h1>
  <img src="assets/logo.png" alt="Syncra" width="40" align="top">
  Syncra - Plex Playlist Manager
</h1>

🎵 **Advanced playlist management for Plex Media Server with streaming service integration**

## 📸 Screenshots

### Home
![Home](https://github.com/user-attachments/assets/980e7ef3-069f-4f2a-9ab1-4658130fb02e)

### Advanced Playlist Editor
![Playlist Editor](https://github.com/user-attachments/assets/a6703fa8-dbd7-4dca-8796-cc57ee9dd962)

### Sync Manager
![Sync Manager](https://github.com/user-attachments/assets/c68ab5eb-dab6-493a-b51f-df90b3206dd5)

### Tools & Utilities
![Tools & Utilities](https://github.com/user-attachments/assets/012e5289-6fab-4d86-baf3-cc044d1d9979)

## ✨ Features

- 🎨 **Five colour themes** — Midnight, Carbon (OLED), Slate, Aurora and a light Daylight theme, switchable in Settings without a restart
- 🖼️ **Cover-art playlist wall** — browse your playlists as posters with track counts and playing time, with a filter box and a compact list view when you want one. Rename any playlist with F2 or the right-click menu
- 🔄 **Sync Manager** with cover art, per-service badges, and an at-a-glance summary of what is configured and when it last ran
- 🎛️ **Advanced Playlist Editor** with search, filtering, and drag-and-drop reordering
- 🔄 **Auto-Sync** from Spotify, Deezer, Tidal, YouTube, and ListenBrainz playlists
- 🎧 **Sonic Discovery** — build playlists from Plex's own audio analysis: "More Like This" from any track, or a **Sonic Adventure** that plots the gradual path between two tracks. Entirely local, no external service
- 🎯 **Missing Tracks workspace** - a running, deduplicated list of everything your imports couldn't find, with re-check and CSV export
- 🧠 **Match Memory** - Syncra learns from your manual match corrections and stops asking twice
- 👁️ **Sync Preview & Revert** - see exactly what a sync will change before it runs, and undo it afterwards
- 🔀 **Playlist Merger** with intelligent duplicate detection
- 🛠️ **Tools & Utilities** including backup, restore, and library analysis
- 🧬 **File Metadata Fixer** (feature-flagged) using MusicBrainz + Cover Art Archive proposals
- 🍎 **Apple Music XML Import** with playlist preview and optional rating sync
- ⚡ **Lightning-fast performance** with smart caching system
- 🎯 **Precise track positioning** - move any track to any position instantly
- 🔍 **Duplicate track finder** across your entire library
- 📊 **Library statistics** and playlist analytics

## 🚀 Download

Get the latest version for your platform from the [Releases](https://github.com/jaylex32/syncra/releases) page:

- **🪟 Windows**: `Syncra-Windows.exe`
- **🍎 macOS**: `Syncra-macOS`
- **🐧 Linux**: `Syncra-Linux`

## 📋 Installation

1. **Download** the appropriate version for your operating system
2. **Run** the executable (no installation required!)
3. **Connect** to your Plex server using your credentials
4. **Start managing** your playlists like a pro!

## 🎯 Quick Start

1. **Connect to Plex**: Enter your server details in the Connection tab
2. **Fetch Playlists**: Click "Fetch Playlists" to load your collection as a wall of cover art
3. **Edit Playlists**: Double-click any cover to open the advanced editor; tick the box on a cover to include it in delete, export and sync actions
4. **Sync from Streaming**: Paste Spotify/Deezer/Tidal/YouTube/ListenBrainz URLs to auto-sync
5. **Explore Tools**: Check out the Tools & Utilities for advanced features

## ⌨️ Headless Sync (CLI)

Run syncs without opening the app — for Task Scheduler, cron, systemd, or a container
alongside Plex. Configure your playlists once in the Sync Manager, then:

```bash
syncra --list                    # show configs and last run
syncra --sync-all                # sync everything
syncra --sync "Baila Reggaeton"  # sync one playlist (repeatable)
syncra --sync-all --dry-run      # preview changes, write nothing
syncra --sync-all --json         # machine-readable output
syncra --sync-all --log-file sync.log   # append output to a file
```

Running from source, use `python main.py --sync-all`.

Headless runs are recorded in the same history the app reads, so they show up in
**Sync History** and can be reverted from the UI. Exit codes: `0` success, `1` failure,
`2` partial (some playlists synced, some failed).

**Windows Task Scheduler example** — sync every night at 3am:

```
Program:   C:\Path\To\Syncra-Windows.exe
Arguments: --sync-all --log-file "%LOCALAPPDATA%\Syncra\sync.log"
```

> **Use `--log-file` for scheduled runs.** Syncra ships as a windowed executable, so
> when it is launched without a terminal there is nowhere for it to print. The sync
> still runs correctly, but you would have no record of it. Run from a terminal and
> output appears normally — the CLI attaches to the calling console.

## 🔄 Auto-Sync Setup

1. Go to **Sync Manager** tab
2. Select a Plex playlist
3. Enter a **Spotify/Deezer/Tidal/YouTube URL**
4. Set **sync interval** (hourly, daily, etc.)
5. **Enable auto-sync** and let Syncra keep your playlists updated!

## 🧬 Metadata Fixer

- File Metadata Fixer uses MusicBrainz + Cover Art Archive suggestions and writes selected changes to local audio file tags.
- It never modifies local files unless you explicitly apply reviewed proposals.
- It is feature-flagged by default. Enable it in `app_config.json`:
  - `features.metadata_fixer = true`

### 📋 System Requirements
- **Windows**: Windows 10/11 (64-bit)
- **macOS**: macOS 10.14+ (Mojave or later)  
- **Linux**: Ubuntu 18.04+ or equivalent
- **All platforms**: Plex Media Server with music library

## 📱 Supported Streaming Services

- 🎵 **Spotify** (playlists, albums, tracks)
- 🎶 **Deezer** (playlists, albums, tracks)  
- 🎧 **Tidal** (playlists, albums, tracks)
- ▶️ **YouTube / YouTube Music** (public playlists, no sign-in)
- 🧠 **ListenBrainz** (import/export playlists)
- 🍎 **Apple Music XML exports** (library/playlists snapshot import)
- 📁 **M3U/M3U8 files** (local and remote)

## 🏗️ Development

Built with:
- **Python 3.11** with PyQt6 for the interface
- **PlexAPI** for Plex server communication
- **Spotipy** for Spotify integration
- **Advanced fuzzy matching** for cross-platform track identification

## Telegram Group

- Join me at the Telegram group for Requests and ideas: https://t.me/+I1Yyz6WdBxsyMzQx

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⭐ Show Your Support

 - If you like my work and want to buy me a coffee to support me, you can do so here: https://buymeacoffee.com/jayross


If Syncra makes managing your Plex playlists easier, please:
- ⭐ **Star this repository**
- 🔄 **Share with fellow Plex users**
- 💝 **Contribute** improvements or suggestions

---

*Made with ❤️ for the Plex community*
