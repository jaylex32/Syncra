# Changelog

## v2.22.1 - 2026-08-23

Hotfix. **v2.22.0 would not start** -- it failed on launch with
`ImportError: cannot import name 'legacy_main' from 'syncra.app'`. Please update.

### 🚨 Fixed: the packaged app could not start
- One line used an f-string with its own quote character nested inside the replacement
  field. That is PEP 701, valid from **Python 3.12** and a `SyntaxError` before it --
  and the release workflow builds on **Python 3.11**.
- PyInstaller does not fail when a module will not compile; it logs and carries on. So
  `syncra/app/legacy_main.py` was silently left out of the executable. The shipped
  build contained 6 of the app's 47 modules, and died at startup pointing at an import
  error that had nothing to do with the real cause.
- Development and the test suite both ran on Python 3.12, so every test passed and the
  build went green.
- Added a `compileall` step to both build workflows, so a file that will not compile
  now fails the build instead of quietly shipping a broken binary.
- Added a test that compiles every source file with the minimum supported Python
  (3.11), and a second that fails if the workflows move to a different version without
  that minimum being updated.

## v2.22.0 - 2026-08-23

Five colour themes including a light one, YouTube playlist import, sharing playlists
with the other accounts on your server, exporting a playlist as real audio files, and
a fix for an import that renamed users' own files.

### 🎨 Colour Themes
- **Added five colour themes**, chosen in Settings and applied instantly without a restart: **Midnight** (the original navy and cyan), **Carbon** (near-black, for OLED screens and dark rooms), **Slate** (neutral grey with a teal accent), **Aurora** (deep indigo with magenta), and **Daylight** (a proper light theme). The choice is remembered between launches.
- Every colour now comes from a named palette describing the *role* it plays -- "the surface inputs sit on", not "dark navy" -- which is what lets the light theme invert cleanly.
- **Roughly 330 hardcoded colours were removed**, including 199 CSS declarations buried in inline `setStyleSheet` calls in the main module. Each was a spot that would have kept its old colour forever; labels that used to carry an inline colour now use a semantic `status` property instead, so their colour follows the theme and updates live.
- **Fixed: a light theme showed black panels behind styled content.** The stylesheet only covers what Syncra styles by name; anything Qt paints itself -- scroll-area viewports, message boxes, native dialogs -- reads the QPalette, which was still the dark default. The palette is now built from the theme too.
- Generated playlist tiles, the cover grid's cards, checkboxes and hover washes are all painted from the live palette rather than fixed values.
- Midnight renders byte-identical to the previous stylesheet, so the default look is unchanged.
- Streaming-service badges deliberately keep their brand colours in every theme; a local file or unknown source gets a neutral chip that follows the palette.
- A regression guard in the test suite fails if a raw hex colour reappears in UI code, since that is exactly how a theme develops holes.

### 🎵 Exported MP3s Now Carry Their Metadata
- **Fixed: exporting to MP3 produced files with no tags and no artwork.** Plex's transcoder returns a bare stream — the only frame it set was `TSSE`, naming the encoder — so every converted track arrived with no title, artist, album, track number or cover. Exports to *original* format were unaffected, since those are a byte copy of the source file.
- Exported MP3s are now tagged with title, artist, album, album artist, track and disc number, genre, release year, and embedded front cover art.
- Tags are written as **ID3v2.3**, which is what older car head units and cheap players read; v2.4 is frequently ignored by them.
- Album art and release year are fetched **once per album** and reused across its tracks, so a 12-track album costs one artwork download rather than twelve.

### 🖼️ Custom Playlist Covers
- **Fixed: the playlist wall showed the auto-generated composite even when a playlist had a custom cover.** The `playlists()` listing reports the 4-panel composite as the playlist's thumb regardless of what poster is actually selected, so a custom cover you uploaded never appeared. 25 of 60 playlists on the test server were affected.
- The selected poster is now resolved per playlist in the background, on the same worker pool as the artwork. The composite still paints immediately, and a custom cover replaces it a moment later, so nothing feels slower.
- The lookup is queued *before* the cached-composite fast path returns; queued after it, an already-cached composite meant the custom cover was never looked up at all.

### 📁 More Export Folder Layouts
- Export with audio files now offers seven layouts instead of two: one flat folder, Artist, Album, Artist/Album, Playlist, Playlist/Artist, and Playlist/Artist/Album.
- The dialog shows the resulting path for the selected layout, so the choice is concrete before you start.
- Track numbering follows the layout: inside an album folder the track's own number is used, otherwise its position in the playlist.
- Playlist-prefixed layouts keep the `.m3u` at the destination root, so several playlists can be exported side by side onto one drive without colliding.

### ▶️ YouTube Playlist Import
- **Added importing public YouTube and YouTube Music playlists.** Paste a playlist link anywhere a Spotify/Deezer/Tidal link already works — Streaming Import, and as a Sync Manager source so it keeps syncing. No sign-in is needed for public playlists. Only metadata is read; nothing is downloaded from YouTube.
- **Titles are cleaned before matching, carefully.** On a real 185-track playlist, 40% of titles carried upload furniture — "(Official Music Video)", "(Official 4K Video)", "[HD Remaster]", a trailing bare "HD". Feeding those to the matcher loses tracks the library actually has.
  - Blanket bracket-stripping would be worse: the same playlist contains "(dub mix)", "(Rah Mix)", "(Naive Melody)", "(No Can Do)" and "(Are Made Of This)", which are part of the real song. A bracketed group is removed only when everything meaningful inside it is production noise.
- **The uploader is not the artist.** On regular YouTube playlists the artist field is the channel that posted the video: "Prince - Purple Rain" came through credited to *"The Codfather"*, and "George Benson - Give Me The Night" to *"RHINO"*. Where the title itself carries an "Artist - Title" prefix, that prefix now wins, so those tracks are attributable. Dashes inside brackets are not treated as a split point, so "Danger Zone (Official Video - Top Gun)" stays intact.
- Measured against a real library, 87% of a 40-track sample resolved on the first pass; the remainder are remix and "feat." variants that Smart Matching and Match Memory already exist to handle.
- Album-style and private links fail with a readable explanation instead of an internal parse error.
- Adds a dependency on `ytmusicapi`, bundled into the packaged builds.

### 👥 Share Playlists With Your Household
- **Added sharing a playlist with the other accounts on your server.** Plex playlists belong to the account that created them, and Plex itself offers no way to hand one to another user — so on a server with a family, every playlist the admin builds is invisible to everyone else. Right-click a playlist and pick who should get their own copy.
- Choose what happens if they already have a playlist by that name: leave theirs alone, add only the tracks they are missing, or replace it (confirmed separately, since that deletes something belonging to someone else).
- Each account is handled independently and reported on its own row, so one person failing never hides what happened to the others.
- One request per user rather than one per track: playlist creation only needs rating keys, so sharing a 138-track playlist with seven people is seven writes, not a thousand lookups.

### 💾 Export Playlists With Their Audio
- **Added exporting a playlist as actual audio files**, not just an `.m3u`. The existing export writes server-side paths like `\\Desktop-u78huhb\f\Music Masters\...`, which mean nothing on a USB stick — nothing plays. This copies the audio into a folder alongside a playlist with relative paths, so it works in a car, on a phone, or in any player pointed at the folder.
- **Your Plex server does the converting**, so nothing needs installing locally. A 24-track FLAC playlist is 771 MB; at MP3 192 kbps it is about 146 MB. Originals, 320, 192 and 128 kbps are all offered, with the saving shown before you start.
- Flat numbered folder or Artist/Album subfolders, plus a size limit for the target device (1 GB up to 32 GB).
- Filenames are sanitised for FAT32/exFAT, which is what USB sticks and SD cards actually use — `AC/DC` and `What?` are ordinary music metadata and illegal filenames. Trailing dots and spaces are stripped too, since Windows drops them silently and would otherwise collapse two tracks into one file.
- Name collisions are resolved while planning rather than at write time, so two tracks with the same name cannot quietly overwrite each other.
- Cancelling keeps what was already written and still writes a playlist for it.

### 🖼️ Branding
- New application icon.

### 🐛 Fixes
- **Fixed: importing a `.m3u8` renamed the user's own file.** Before uploading, the importer ran `os.rename()` on the source playlist to change its extension to `.m3u` — permanently altering a file the app had only been asked to read. Importing a folder did it to every `.m3u8` in it. Originals are now left untouched; the upload works from a temporary copy instead.
  - The rename was never needed. The direct upload posts the playlist under a filename it builds itself (`<playlist name>.m3u`), so the name on disk never reached Plex. The extension only mattered to the local-server path fallback, which is now handed the temp copy.
  - Only affected imports with **Path Matching** selected; the Smart Matching path returned before the rename.
  - Applies to every import route — single file, whole folder, backup restore, and playlists built from selected local tracks — since all of them go through the same upload function.
- Temp upload copies are now always written with a `.m3u` extension, and the temp-folder cleanup prunes stale `.m3u8` copies left by earlier versions instead of ignoring them.

## v2.21.0 - 2026-08-09

A cover-art overhaul of the Playlists and Sync Manager pages, playlist renaming, Sonic
Discovery, a headless sync CLI, a much faster duplicate scan, and a set of startup and
logging fixes — including one that meant the application log file was never written.

### 🪵 Logging and Startup Noise
- **Fixed: the log file was never written.** Importing the main module constructs the credential manager at module scope, which logs — and a logging call with no handlers installed makes Python run `basicConfig()` implicitly. By the time `setup_logging()` ran, the root logger already had a handler, and `basicConfig()` is documented to do *nothing* in that case. So the `FileHandler` was never installed: `plex_playlist_manager.log` stayed empty, and every diagnostic the app thought it was recording went nowhere.
- **Fixed: every console line printed twice**, once as `WARNING:root:...` and once timestamped — the two handlers left behind by the same problem.
- **Fixed: two "Skipping save_config()" warnings on every launch.** Loading the configuration sets the M3U matching checkboxes, whose change handler saves — which ran before the load had finished, tripping the guard that protects against overwriting settings with empty defaults. Saving is now suspended for the duration of a load, so the signals fired while populating widgets no longer try to write back what was just read. The guard itself is unchanged and still fires outside a load.

### 🏷️ Rename Playlists
- **Added renaming for existing playlists** — right-click a cover, or press **F2**. The app previously had no way to rename a playlist at all; the only "Rename" prompts were import-time collision dialogs offering to rename an *incoming* playlist before uploading it.
- **A rename carries its sync configuration with it.** Sync configurations are keyed by playlist name, so renaming without updating the configuration would have silently orphaned it and the next sync would look for a playlist that no longer exists.
- Duplicate names are refused, surrounding whitespace is collapsed (Plex keeps padding, which makes two playlists look identical in a list), and a server refusal is reported rather than leaving the UI showing a name that was never applied.
- Uses `editTitle()`; `Playlist.edit()` is deprecated in plexapi 4.17 and emits a warning. Verified against Plex 1.43.3.

### 🔄 Sync Manager Rebuild
- **Two-column layout.** The page was a single stack of six cards, so on a wide monitor the configuration table was a few rows tall with everything else pushed off-screen. Configurations and manual actions now take the main column while automation settings and the log move into a side column, and the progress bar spans the full width beneath both.
- **A summary strip across the top** — configured count, auto-sync state, next scheduled run, and last successful sync — so the page answers "is anything actually syncing?" without reading four separate cards.
- **Playlist cover art in each row**, reusing the Playlists page's cache, plus a colour-coded service badge for Spotify, Deezer, TIDAL, ListenBrainz and local files.
- **Fixed: the Delete button was clipped.** Source and Actions were both set to stretch, so they fought over the same space. Source is now the only stretch column, and sections have a minimum width so it can no longer collapse to 47px.
- **Fixed: per-row buttons were hardcoded Material green and red** — the one palette the rest of the app never uses. They take the shared primary and danger variants now, and fit the row height instead of overflowing it.
- Row-building code existed in three near-identical copies; they now share one `add_sync_config_row`.
- Automatic Sync stacks its label and field like Scheduled Sync does, instead of clipping its own checkbox label in the narrower column.

### 🖼️ Playlists as a Cover Wall
- **The Playlists page is now a grid of album art** instead of a column of "Title (N tracks)" strings. Each playlist is a card with its Plex poster, its name, and its size and playing time.
- **Track counts and durations appear immediately.** `leafCount` and `duration` already arrive with the playlist listing, so "138 tracks · 9h 7m" is shown for free on first paint — the old "click to load tracks..." placeholder was only ever there because the count was assumed to be unknown until you clicked.
- **Covers load in the background and are cached on disk.** A poster is ~29KB and ~126ms from the server, so a 60-playlist wall would be about 7.5s of network time on every visit. They are now fetched four at a time and re-read from a bounded LRU cache afterwards, so later visits paint instantly. The cache key ignores the Plex token, so signing in again does not invalidate it. "Clear Cache" clears the art too.
- **Playlists with no artwork get a generated tile** — a gradient derived from the title with the playlist's initials — so the wall never has holes in it. The colours are stable for a given playlist between launches.
- **Tiles stretch to fill the window.** Qt's icon grid uses fixed cells and leaves whatever does not divide evenly as a dead column on the right; the grid now recomputes its cell size so the covers stay flush with both edges at any width, and re-tiles when the scrollbar appears rather than being left one column short.
- **Covers shrink as the window narrows**, so a small window shows more of them rather than two oversized tiles. Column count is chosen by rounding rather than flooring, with a floor on how small a cover may get.
- **Fixed: the Playlists page could not be narrowed at all.** One long non-wrapping label gave it a ~1500px minimum width, and the five action buttons in a plain row added their widths together for another ~980px, so narrowing the window produced a horizontal scrollbar instead of a reflow. The label wraps and the actions use a flow layout that wraps onto a second line; the page's minimum is now 411px and the grid actually reflows.
- Added a **filter box** and a **Grid / List** switch; the choice is remembered. List mode is the previous compact view, and it skips downloading art nobody is going to see.
- Selection is unchanged: tick the box on a cover to include it in delete, export and sync actions.
- **Fixed: a ticked row was invisible.** The theme styled `QCheckBox::indicator` but nothing for item views, and once a stylesheet is active Qt stops drawing the native checkmark — so a checked playlist looked exactly like an unchecked one. This affected every checkable list and tree in the app, not just the Playlists page.

### 📦 Packaging and Window Identity
- **Fixed: dialogs without an explicit title showed "python".** Nothing set `QApplication.applicationName()`, so Qt fell back to the executable basename — visible on the duplicate-deletion progress window. The app now sets its name, display name and organisation at startup, which fixes the fallback for every window.
- **Fixed: the window icon never loaded in a build.** It was loaded as `QIcon('Syncra Icon.ico')` — a bare relative path that resolves against the working directory — and the file was not in the PyInstaller `datas` at all, only set as the executable's own file icon. It is now bundled and loaded through `resource_path()`, and applied to the QApplication so every dialog inherits it.
- **Fixed: `resource_path()` fell back to the current working directory**, so bundled resources only resolved when the app happened to be launched from the project root. It now derives the project root from the module location.
- The deletion progress window has an explicit title and icon.

### 🔍 Library Duplicate Scan
- **Roughly 30x faster.** The scan made two HTTP round trips for every track — `track.artist()` and `track.album()`, measured at 25ms and 20ms against a live server — to read names the search response already contained. On a 14,753-track library that alone was about 11 minutes; it is now free via `grandparentTitle` / `parentTitle`.
- **Playlist membership is indexed once.** It previously re-fetched every playlist's contents for every duplicate track (60 playlists x 71ms = 4.2s *per track*, so minutes to hours on a real result set). One pass now builds a ratingKey lookup and every track is answered from it.
- A full scan of a 14,753-track library with playlist checking now takes **~72 seconds** and finds 1,976 duplicate groups.
- Added a **Stop and Show Results** button. Stopping keeps everything found so far and opens the manager with it, instead of discarding the work.
- Duplicate matching now uses the same fingerprint as Match Memory and Missing Tracks, so remaster suffixes, featured-artist credits and punctuation no longer hide a duplicate.
- Groups are ordered largest first, so the worst offenders are at the top.
- Closing the app during a scan now asks the thread to stop before falling back to `terminate()`, which could previously kill it mid-request.
- **Rebuilt the results screen.** It was rendering in hardcoded white and light green against the dark app, with near-invisible text, and gave each track a ~230px card so only two or three copies fitted on screen. It is now a themed tree with one row per track, showing album, quality, size, duration, playlists and file path in sortable columns, plus a filter box and expand/collapse.
- Building the results at real scale (1,976 groups) went from **6.4s to 0.11s** by inserting tree rows in bulk instead of one at a time.
- **Fixed: bitrate always showed "Unknown".** `track.bitrate` is always None; the value lives on the Media element. The quality ranking behind "keep the best copy" was therefore comparing zeroes, and now compares real bitrates and codecs.
- **Fixed: Auto-Select never ticked anything.** `update_ui_selections()` was an empty stub, so the count changed but every checkbox stayed clear.
- Sizes are formatted per unit, so a large total reads "101.8 GB" rather than "~104199.7MB".

### 🎧 Sonic Discovery
- Added playlist generation driven by **Plex's own audio analysis** of your library. Nothing is sent to an external service and there are no rate limits — the server already knows what your files sound like.
  - **More Like This** — seed with **one track or many**, and get a blended mix, with a similarity control from "Very close" to "Adventurous".
    Plex's `/nearest` endpoint answers per track, so several seeds are merged client-side with reciprocal rank fusion: a track sitting near *several* seeds outranks one sitting very near a single seed, which makes the result sound like the set rather than like whichever seed was queried first. A seed that fails or has no neighbours is skipped and reported rather than sinking the whole mix.
  - **Sonic Adventure** — pick a start and an end track and Plex plots the gradual path between them.
- The result is an **editable playlist workbench**, not a fixed list:
  - **Lock** any track and press Generate again — locked rows stay put while the rest reshuffles.
  - **Variety** control: *Focused* reproduces the same mix every time, *Balanced* and *Surprising* sample a widening window so each Generate gives something new.
  - **Remove**, **Move Up/Down**, **Shuffle** and **Add From Search** to hand-finish the list before saving.
  - **Hide repeats of the same song** collapses a recording that exists on a single, an album and a compilation into one entry. Deduplicating on Plex ratingKey alone missed these, which is why duplicates were showing up.
  - Running total of track count and playing time, and the saved playlist is whatever is on screen, including manual edits.
- The dialog is laid out in **two columns** — controls in a fixed-width panel on the left, the playlist filling the right — behind a draggable splitter. Stacking everything vertically had given the setup card most of the window and left the playlist showing two rows, so seeing the result meant scrolling or making the window very tall.
- Both are available from Tools & Utilities, and **Find Similar Tracks…** was added to the track right-click menu in the Playlist Editor. The editor already allowed multi-select, so every highlighted row becomes a seed and the menu says how many.
- Results are previewed in a table before anything is written; saving creates a normal Plex playlist.
- Generation runs on a worker thread — on a large library Plex can take several seconds and the dialog previously would have appeared frozen.
- Track selection is a **search-as-you-type picker that matches artists and albums, not just track titles** — typing "cosa nuestra" finds the album's tracks, "feid" finds that artist's tracks, even where the text appears in neither track title. Built on Plex's unified `hubSearch` (~67ms against a live library, versus ~1270ms for an `artist.title` track filter), with artist and album hits expanded into their tracks. Keystrokes are debounced into a single request and out-of-order responses from a slower earlier query are discarded.
- Similarity presets are anchored on the server's own default (`maxDistance=0.25`, per the PMS API docs for `/library/metadata/{id}/nearest`) rather than a guessed value.
- Verified against Plex 1.43.3. Artist-level `station()`, `popularTracks()` and `sonicallySimilar()` return nothing usable on that version — the artist-radio endpoint 404s even when requested directly with a correctly formed URL — so nothing depends on them. When a library has not been analysed, the dialog explains how to fix it instead of failing silently.
### ⌨️ Headless Sync (CLI)
- Added a command-line entry point so syncs can run without opening the app, driven by Task Scheduler, cron, systemd, or a container next to Plex. Previously auto-sync only ran while the main window was open, which made the Sync Manager's intervals and schedules ineffective once you closed it.
  - `syncra --list` — show sync configurations and their last run
  - `syncra --sync-all` — sync every configured playlist
  - `syncra --sync "Name"` — sync one playlist (repeatable)
  - `--dry-run` — resolve and diff without writing to Plex
  - `--json` — machine-readable output for logging
  - `-v` — stream per-track progress to stderr
  - `--log-file PATH` — append output to a file, for scheduled runs with no console
- Headless runs write to the same sync-history database as the app, so they appear in Sync History and can be reverted from the UI. Unmatched tracks are added to Missing Tracks exactly as they are from a manual run.
- **Fixed: the CLI produced no output at all from the packaged binary.** Syncra is built with PyInstaller `--windowed`, which yields a GUI-subsystem executable whose `stdout`/`stderr` are `None`, so every message was silently discarded. The CLI now attaches to the calling terminal's console on Windows, and `--log-file` covers runs that have no console at all.
- Exit codes: `0` success, `1` failure, `2` partial (some playlists synced, some failed).
- **Fixed: Track Matching Filters were never saved.** The smart-filter options existed only as checkbox state, so every launch silently reset them to defaults. They are now stored under `match_filters` in `app_config.json` and restored on load.
- Decoupled the sync engine from the UI: the M3U matching mode, ListenBrainz token, and matching filters are resolved into a `SyncOptions` value object at the start of a run instead of being read off parent widgets mid-sync. This is what makes a GUI-less run possible, and makes the sync path testable for the first time.
### 🚑 Startup Reliability
- **Fixed the app hanging on the loading screen when saved Plex credentials stopped working.** Auto-connect was being dispatched during window construction (the splash screen's `processEvents()` call fired the pending zero-delay timer early), so a rejected token opened an error dialog parented to a window that had not been shown yet. That dialog started a nested modal loop behind the always-on-top splash, where it was invisible and un-dismissable, and the main window could never finish loading.
- Auto-connect now runs only after the main window is visible and the splash has closed.
- Connection failures are now classified with actionable guidance instead of a raw exception string: rejected credentials, connection timeout, unreachable host, and wrong endpoint each get their own message.
- A rejected token is cleared automatically, and the app jumps to the Connection page so the next launch asks for credentials instead of failing silently forever. A network failure no longer discards a working token.
- Connection problems now appear in a persistent banner on the Connection page rather than only in a modal dialog.
- Added a 10-second Plex connection timeout (plexapi defaults to 30s per request), so an unreachable or renamed server fails fast instead of appearing frozen.
- Startup errors of any kind now close the splash and report, instead of leaving it stranded on screen.
- Fixed log records containing emoji being silently dropped on Windows by forcing UTF-8 on the log file handler.

### 🎯 Missing Tracks
- Added a **Missing Tracks** workspace (Tools & Utilities) that accumulates every track an import or sync could not find, deduplicated across runs, with the playlists that wanted it and a request counter.
- Added **Re-check Library**, which re-runs the matcher over the whole list after you add music and marks anything now present as resolved.
- Added per-track resolve / ignore / remove actions, text and CSV export for use as a shopping list, and clipboard copy.
- Unmatched tracks are now captured from M3U smart imports, streaming imports, and playlist syncs, instead of being shown once in a truncated dialog and discarded.
- Added a Missing Tracks count to the Home dashboard.

### 🧠 Match Memory
- Syncra now remembers manual match corrections. Confirming or picking a track in the match dialogs stores that decision, and later imports of the same track resolve the same way without asking again.
- Remembered decisions also cover "this track is not in my library", so known-missing tracks stop being re-guessed.
- Decisions are scoped per Plex library and survive formatting differences in the source (remaster suffixes, featured-artist credits, punctuation).
- Stale decisions pointing at deleted tracks fall back to normal scoring automatically.
- Added a **Match Memory** dialog (Tools & Utilities) to review, count usage of, and forget learned decisions.

### 🕘 Sync Preview, History, and Revert
- Added **Preview Changes** to the Sync Manager: resolves every source track and reports exactly what would be added, removed, and left unmatched, without writing anything to Plex.
- Every sync run now records the playlist contents before and after it ran.
- Added a **Sync History** dialog with a per-run diff of added and removed tracks.
- Added **Revert This Run**, which restores a playlist to its contents from before a sync — a safety net for `Clear on Sync`. Reverts abort safely rather than clearing a playlist they cannot restore.

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
