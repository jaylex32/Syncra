"""Headless entry point for Syncra.

Auto-sync previously only ran while the main window was open, which made the Sync
Manager's intervals and schedules useless the moment you closed the app. This module
runs the same sync engine from a terminal so it can be driven by Task Scheduler, cron,
systemd or a container next to Plex.

Runs are recorded in the same sync-history database the GUI reads, so a headless run
shows up in Sync History and can be reverted from the UI like any other.

    syncra --list
    syncra --sync-all
    syncra --sync "Baila Reggaeton"
    syncra --sync-all --dry-run --json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

# Qt still has to load -- the sync code lives alongside the widgets -- but nothing is
# ever shown, so force the offscreen platform before Qt is imported. Without this a
# machine with no display (a server, a container, a Task Scheduler session) would fail
# at import rather than run.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_PARTIAL = 2


class _Tee:
    """Write to several streams, tolerating any that are missing or closed."""

    def __init__(self, *streams):
        self._streams = [stream for stream in streams if stream is not None]

    def write(self, text):
        for stream in self._streams:
            try:
                stream.write(text)
            except Exception:
                pass
        return len(text)

    def flush(self):
        for stream in self._streams:
            try:
                stream.flush()
            except Exception:
                pass

    def isatty(self):
        return False


def attach_parent_console():
    """Reattach stdio when running as a frozen windowed build on Windows.

    Every Syncra build is produced with PyInstaller `--windowed`, which yields a
    GUI-subsystem executable with no console: `sys.stdout` and `sys.stderr` are None
    and every print silently vanishes. Borrowing the calling terminal's console makes
    `Syncra.exe --list` behave like a normal command. Returns True if it worked.
    """
    if sys.platform != "win32":
        return False
    if sys.stdout is not None and sys.stderr is not None:
        return False  # already have usable streams (running from source)
    try:
        import ctypes

        attach_parent = -1
        if not ctypes.windll.kernel32.AttachConsole(attach_parent):
            return False
        # CONOUT$/CONIN$ address the attached console directly.
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        return True
    except Exception:
        return False


def configure_output(log_path=None):
    """Guarantee stdout/stderr are writable, optionally teeing to a log file.

    Without a console (a scheduled task, a service) a frozen build has nowhere to
    write, so a run leaves no trace of what it did. --log-file gives those runs an
    audit trail.
    """
    attach_parent_console()

    log_stream = None
    if log_path:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
            log_stream = open(log_path, "a", encoding="utf-8", buffering=1)
        except Exception:
            log_stream = None

    # A frozen windowed build leaves these as None; print() then silently no-ops.
    sys.stdout = _Tee(sys.stdout, log_stream)
    sys.stderr = _Tee(sys.stderr, log_stream)
    return log_stream


def _load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
    except Exception as error:
        logging.error(f"Could not read {path}: {error}")
    return default


class HeadlessSyncRunner:
    """Drives SyncThread's logic synchronously, with no event loop."""

    def __init__(self, verbose=False, emit_json=False):
        self.verbose = verbose
        self.emit_json = emit_json
        self.results = []
        self.errors = []
        self.previews = []

    # ------------------------------------------------------------------ output

    def log(self, message):
        """Progress goes to stderr so --json keeps stdout machine-readable."""
        if self.verbose and not self.emit_json:
            print(message, file=sys.stderr, flush=True)

    def say(self, message):
        if not self.emit_json:
            print(message, flush=True)

    # ------------------------------------------------------------------- setup

    def connect(self, config):
        from plexapi.server import PlexServer

        from syncra.app import legacy_main

        token = str(config.get("token", "") or "").strip()
        ip = str(config.get("server_ip", "") or "").strip()
        port = str(config.get("server_port", "") or "").strip()
        if not (token and ip and port):
            raise RuntimeError(
                "No saved Plex connection. Open Syncra and connect once so the server "
                "address and token are stored, then re-run."
            )

        self.log(f"Connecting to {ip}:{port} ...")
        return PlexServer(
            f"http://{ip}:{port}", token, timeout=legacy_main.PLEX_CONNECT_TIMEOUT
        )

    # -------------------------------------------------------------------- runs

    def run(self, names, dry_run=False):
        from syncra.app import legacy_main
        from syncra.services.sync_options import SyncOptions

        config = _load_json(legacy_main.CONFIG_FILE, {})
        sync_config = _load_json(legacy_main.SYNC_CONFIG_FILE, {})
        playlists = sync_config.get("sync_playlists", {}) or {}

        if not playlists:
            raise RuntimeError(
                "No sync configurations found. Add one in the Sync Manager first."
            )

        selected = {}
        for name, entry in playlists.items():
            if names and name not in names:
                continue
            selected[name] = {
                "source_url": entry.get("source_url", ""),
                "library_section": entry.get("library_section", config.get("last_section")),
                "clear_before_sync": bool(entry.get("clear_before_sync", False)),
            }

        missing = [name for name in (names or []) if name not in playlists]
        for name in missing:
            self.errors.append(f"No sync configuration named '{name}'")

        if not selected:
            raise RuntimeError("Nothing to sync (no matching configurations).")

        server = self.connect(config)
        options = SyncOptions.from_config(config)

        thread = legacy_main.SyncThread(
            selected, server, parent=None, dry_run=dry_run, options=options
        )
        thread.progress_update.connect(lambda message, _pct: self.log(f"  {message}"))
        thread.sync_complete.connect(self._on_complete)
        thread.preview_ready.connect(self._on_preview)
        thread.error.connect(self._on_error)

        verb = "Previewing" if dry_run else "Syncing"
        self.log(f"{verb} {len(selected)} playlist(s)...")
        # run() directly rather than start(): no event loop, no thread, so signals fire
        # synchronously and the process exits when the work is genuinely finished.
        thread.run()
        return self.report(dry_run)

    def _on_complete(self, name, added, total):
        self.results.append({"playlist": name, "added": added, "source_tracks": total})

    def _on_preview(self, name, preview):
        changes = preview.get("changes", {})
        self.previews.append(
            {
                "playlist": name,
                "before": changes.get("before_count", 0),
                "after": changes.get("after_count", 0),
                "added": len(changes.get("added", [])),
                "removed": len(changes.get("removed", [])),
                "unmatched": len(preview.get("unmatched", [])),
            }
        )

    def _on_error(self, message):
        self.errors.append(str(message))

    # ------------------------------------------------------------------ report

    def report(self, dry_run):
        payload = {
            "mode": "preview" if dry_run else "sync",
            "results": self.previews if dry_run else self.results,
            "errors": self.errors,
        }
        if self.emit_json:
            print(json.dumps(payload, indent=2), flush=True)
        elif dry_run:
            for row in self.previews:
                self.say(
                    f"{row['playlist']}: {row['before']} -> {row['after']} tracks "
                    f"(+{row['added']} / -{row['removed']}, {row['unmatched']} unmatched)"
                )
            if not self.previews:
                self.say("No changes to preview.")
        else:
            for row in self.results:
                self.say(f"{row['playlist']}: added {row['added']} track(s)")
            if not self.results:
                self.say("No playlists were synced.")

        for message in self.errors:
            print(f"error: {message}", file=sys.stderr, flush=True)

        if self.errors:
            return EXIT_PARTIAL if (self.results or self.previews) else EXIT_ERROR
        return EXIT_OK


def list_configs(emit_json=False):
    from syncra.app import legacy_main

    sync_config = _load_json(legacy_main.SYNC_CONFIG_FILE, {})
    playlists = sync_config.get("sync_playlists", {}) or {}

    if emit_json:
        print(json.dumps({"sync_playlists": playlists}, indent=2), flush=True)
        return EXIT_OK

    if not playlists:
        print("No sync configurations. Add one in the Sync Manager.", flush=True)
        return EXIT_OK

    width = max(len(name) for name in playlists)
    print(f"{'PLAYLIST'.ljust(width)}  LAST SYNC            SOURCE", flush=True)
    for name, entry in playlists.items():
        last = str(entry.get("last_sync", "") or "never")
        source = str(entry.get("source_url", "") or "")
        print(f"{name.ljust(width)}  {last:<20} {source}", flush=True)
    return EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(
        prog="syncra",
        description="Run Syncra playlist syncs without opening the app.",
    )
    parser.add_argument("--sync-all", action="store_true",
                        help="sync every configured playlist")
    parser.add_argument("--sync", metavar="NAME", action="append", default=[],
                        help="sync one playlist by name (repeatable)")
    parser.add_argument("--list", action="store_true",
                        help="list sync configurations and their last run")
    parser.add_argument("--dry-run", action="store_true",
                        help="resolve and diff without writing anything to Plex")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON on stdout")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="stream per-track progress to stderr")
    parser.add_argument("--log-file", metavar="PATH", default=None,
                        help="append all output to a file (use for scheduled runs, "
                             "which have no console to print to)")
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    # Do this before anything prints: a frozen --windowed build has no stdout, so
    # every message would otherwise disappear.
    configure_output(args.log_file)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
        force=True,
    )

    if args.list:
        return list_configs(emit_json=args.json)

    if not args.sync_all and not args.sync:
        parser.print_help()
        return EXIT_ERROR

    from PyQt6.QtCore import QCoreApplication

    # QCoreApplication, not QApplication: no widgets, no display, but Qt objects and
    # signal delivery still work.
    app = QCoreApplication.instance() or QCoreApplication([])
    try:
        runner = HeadlessSyncRunner(verbose=args.verbose, emit_json=args.json)
        return runner.run(names=list(args.sync), dry_run=args.dry_run)
    except Exception as error:
        logging.debug("Headless sync failed", exc_info=True)
        if args.json:
            print(json.dumps({"results": [], "errors": [str(error)]}, indent=2))
        else:
            print(f"error: {error}", file=sys.stderr)
        return EXIT_ERROR
    finally:
        del app


if __name__ == "__main__":
    sys.exit(main())
