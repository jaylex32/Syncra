import sys

from syncra.app import legacy_main as _legacy_main

if __name__ == "__main__":
    _legacy_main.main()
else:
    # Preserve backward-compatible import semantics (`import main`) for scripts
    # that read/write module globals used by the legacy runtime.
    sys.modules[__name__] = _legacy_main
