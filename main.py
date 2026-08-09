import sys

# CLI flags are dispatched before the GUI module is imported, so a headless run never
# constructs a QApplication or touches the widget stack.
_CLI_FLAGS = {"--sync-all", "--sync", "--list", "--dry-run", "--json", "-v", "--verbose"}

if __name__ == "__main__" and any(arg in _CLI_FLAGS for arg in sys.argv[1:]):
    from syncra.cli import main as _cli_main

    sys.exit(_cli_main())

from syncra.app import legacy_main as _legacy_main

if __name__ == "__main__":
    _legacy_main.main()
else:
    # Preserve backward-compatible import semantics (`import main`) for scripts
    # that read/write module globals used by the legacy runtime.
    sys.modules[__name__] = _legacy_main
