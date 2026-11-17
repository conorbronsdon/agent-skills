#!/usr/bin/env python3
"""Supply-chain guard for GitHub Actions. Stdlib only.

Run from anywhere:  python3 scripts/check_workflow_pins.py

Checks that every third-party `uses:` in .github/workflows and .github/actions
is pinned to a full 40-character commit SHA (tag in a trailing comment), that
every workflow sets top-level `permissions:`, and that Dependabot watches the
github-actions ecosystem so the pins stay current. Before checking the repo it
runs its own parser controls: a tag, a short SHA and a branch ref must be
flagged; a full SHA, a local `./` action and a `docker://` image must not.
Exits 0 when everything passes, 1 otherwise.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITHUB = ROOT / ".github"

USES_RE = re.compile(r"""^\s*(?:-\s+)?uses:\s*["']?([^\s"'#]+)""")
FULL_SHA_RE = re.compile(r"@[0-9a-f]{40}$")


def unpinned_uses(yaml_text):
    """Return every `uses:` ref that is not a full-SHA pin, local action or docker image."""
    bad = []
    for line in yaml_text.replace("\r\n", "\n").split("\n"):
        m = USES_RE.match(line)
        if not m:
            continue
        ref = m.group(1)
        if ref.startswith("./") or ref.startswith("docker://"):
            continue
        if not FULL_SHA_RE.search(ref):
            bad.append(ref)
    return bad


def parser_controls():
    errors = []
    must_fire = (
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-node@49933ea\n"
        "        uses: 'owner/action@main'\n"
    )
    want = ["actions/checkout@v4", "actions/setup-node@49933ea", "owner/action@main"]
    if unpinned_uses(must_fire) != want:
        errors.append("parser control: a tag, short SHA or branch ref was not flagged")
    must_not_fire = (
        "      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0\n"
        "        uses: ./\n"
        "        uses: ./.github/actions/setup\n"
        "        uses: docker://alpine:3.20\n"
        "      # uses: actions/checkout@v4 (a comment, not a step)\n"
    )
    if unpinned_uses(must_not_fire):
        errors.append("parser control: a full SHA, local action or docker image was flagged")
    return errors


def workflow_files():
    files = []
    for sub in ("workflows", "actions"):
        d = GITHUB / sub
        if d.is_dir():
            files += sorted(p for p in d.rglob("*") if p.suffix in (".yml", ".yaml"))
    return files


def repo_checks():
    errors = []
    files = workflow_files()
    if not files:
        errors.append("no workflow files found under .github/")
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(encoding="utf-8")
        for ref in unpinned_uses(text):
            errors.append(f"{rel}: {ref} is not pinned to a full commit SHA")
        if p.parent == GITHUB / "workflows" and not re.search(r"^permissions:", text, re.M):
            errors.append(f"{rel}: no top-level permissions:")
    dependabot = GITHUB / "dependabot.yml"
    if not dependabot.is_file():
        errors.append(".github/dependabot.yml is missing")
    elif not re.search(
        r"package-ecosystem:\s*[\"']?github-actions", dependabot.read_text(encoding="utf-8")
    ):
        errors.append(".github/dependabot.yml does not watch github-actions")
    return errors


def main():
    errors = parser_controls() + repo_checks()
    for e in errors:
        print(f"not ok - {e}", file=sys.stderr)
    if errors:
        return 1
    print(f"ok - {len(workflow_files())} workflow file(s): actions SHA-pinned, "
          "top-level permissions set, dependabot watches github-actions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
