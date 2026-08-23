"""Every source file must compile on the oldest Python the project ships on.

This exists because a released build was broken by a single line:

    item.setForeground(QColor(f'{TOKENS['txt_muted']}'))

Nested same-type quotes inside an f-string replacement field are PEP 701, valid from
Python 3.12 and a SyntaxError before it. Development happened on 3.12 and the CI
builds on 3.11, so:

* every test passed, because the test runner was 3.12;
* the build went green, because PyInstaller does not fail when a module will not
  compile -- it logs and moves on;
* `syncra.app.legacy_main` was silently left out of the executable, and the shipped
  app died at startup with "cannot import name 'legacy_main' from 'syncra.app'",
  which points nowhere near the real cause.

`ast.parse(..., feature_version=(3, 11))` does **not** catch it -- f-string parsing
changed in the tokenizer, which feature_version does not downgrade. The only reliable
check is compiling with the real interpreter, so this test looks for one and skips
loudly when it is unavailable.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import unittest

# Keep in step with .github/workflows/*.yml (python-version) and setup docs.
MINIMUM_PYTHON = (3, 11)

SKIP_PARTS = (
    "/Backup/", "/_pibuild/", "/build/", "/dist/",
    "__pycache__", "/spotlistr_js/", "/playlist_temp/", "/releases/",
)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


def project_sources():
    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        text = str(path).replace("\\", "/")
        if any(part in text for part in SKIP_PARTS):
            continue
        yield path


def find_minimum_interpreter():
    """Locate a Python matching MINIMUM_PYTHON, or None."""
    version = ".".join(str(part) for part in MINIMUM_PYTHON)

    if sys.version_info[:2] == MINIMUM_PYTHON:
        return sys.executable

    launcher = shutil.which("py")
    if launcher:
        probe = subprocess.run(
            [launcher, f"-{version}", "-c", "import sys; print(sys.executable)"],
            capture_output=True, text=True,
        )
        if probe.returncode == 0 and probe.stdout.strip():
            return probe.stdout.strip()

    for name in (f"python{version}", f"python{MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}"):
        found = shutil.which(name)
        if found:
            return found
    return None


class MinimumPythonCompileTests(unittest.TestCase):
    def test_every_source_file_compiles_on_the_minimum_python(self):
        interpreter = find_minimum_interpreter()
        version = ".".join(str(p) for p in MINIMUM_PYTHON)
        if not interpreter:
            self.skipTest(
                f"Python {version} not installed; CI builds on it, so a syntax "
                f"feature newer than {version} would not be caught here."
            )

        script = (
            "import pathlib, sys\n"
            "bad = []\n"
            "for raw in sys.argv[1:]:\n"
            "    p = pathlib.Path(raw)\n"
            "    try:\n"
            "        compile(p.read_text(encoding='utf-8', errors='replace'), raw, 'exec')\n"
            "    except SyntaxError as e:\n"
            "        bad.append(f'{raw}:{e.lineno}: {e.msg}')\n"
            "print(chr(10).join(bad))\n"
        )
        files = [str(p) for p in project_sources()]
        self.assertTrue(files, "no source files found")

        result = subprocess.run(
            [interpreter, "-c", script, *files], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        failures = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(
            failures, [],
            f"these do not compile on Python {version}, which is what CI builds with:\n"
            + "\n".join(failures),
        )

    def test_the_workflows_still_build_on_the_minimum_python(self):
        """If CI moves to a newer Python, MINIMUM_PYTHON must move with it."""
        expected = ".".join(str(p) for p in MINIMUM_PYTHON)
        workflows = list((PROJECT_ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertTrue(workflows, "no workflows found")
        for workflow in workflows:
            text = workflow.read_text(encoding="utf-8")
            versions = re.findall(r"python-version:\s*['\"]?([\d.]+)", text)
            for found in versions:
                with self.subTest(workflow=workflow.name, version=found):
                    self.assertEqual(
                        found, expected,
                        f"{workflow.name} builds on {found} but MINIMUM_PYTHON is "
                        f"{expected}; update MINIMUM_PYTHON so the compile check "
                        f"matches what actually ships",
                    )


class FStringQuoteNestingTests(unittest.TestCase):
    """A fast, interpreter-independent net for the specific syntax that broke a build."""

    NESTED = re.compile(r"f'[^'\n]*\{[^}\n]*'[^'}\n]*'[^}\n]*\}|f\"[^\"\n]*\{[^}\n]*\"[^\"}\n]*\"[^}\n]*\}")

    def test_no_fstring_reuses_its_own_quote_inside_a_replacement_field(self):
        offenders = []
        for path in project_sources():
            # This file quotes the offending line in its own docstring as the
            # worked example, so scanning it would always report itself.
            if path.name == pathlib.Path(__file__).name:
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if self.NESTED.search(line):
                    offenders.append(
                        f"{path.relative_to(PROJECT_ROOT)}:{number}: {line.strip()[:80]}"
                    )
        self.assertEqual(
            offenders, [],
            "same-quote nesting inside an f-string is Python 3.12+ only:\n"
            + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
