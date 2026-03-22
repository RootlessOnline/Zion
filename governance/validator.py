"""
Zion Governance Validator
=========================
Checks that all governance files and prompt files match their recorded SHA256 hashes.
Called at boot. Hard stops if anything has been tampered with.

Usage:
  python governance/validator.py              # check hashes (boot mode)
  python governance/validator.py --rehash     # rebuild hash manifest (run after intentional edits)
  python governance/validator.py --status     # print status without stopping the process
"""

import sys
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent.parent.resolve()
GOVERNANCE_DIR = BASE_DIR / "governance"
MANIFEST_PATH = GOVERNANCE_DIR / "hash_manifest.txt"

# Files that must be hashed and verified at every boot
GOVERNED_FILES = [
    "governance/charter.yaml",
    "governance/permissions.json",
    "governance/validator.py",
    "prompts/manager_prompt.md",
    "prompts/worker_prompt.md",
    "prompts/reviewer_prompt.md",
    "prompts/logger_prompt.md",
    "prompts/watcher_prompt.md",
    "prompts/page_minus_one.md",
]


# ── Hashing ────────────────────────────────────────────────────────────────────

def sha256(path: Path) -> str:
    """Return hex SHA256 of a file's contents."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def build_manifest() -> dict:
    """Hash all governed files and return {relative_path: hash}."""
    manifest = {}
    for rel in GOVERNED_FILES:
        p = BASE_DIR / rel
        if not p.exists():
            print(f"  WARNING: governed file not found — {rel}")
            continue
        manifest[rel] = sha256(p)
    return manifest


# ── Manifest file ──────────────────────────────────────────────────────────────

def save_manifest(manifest: dict):
    """Write manifest to governance/hash_manifest.txt."""
    lines = [
        "# Zion Governance Hash Manifest",
        f"# Generated: {datetime.now(timezone.utc).isoformat()}",
        f"# Files: {len(manifest)}",
        "# Do not edit manually. Run: python governance/validator.py --rehash",
        "",
    ]
    for path, digest in sorted(manifest.items()):
        lines.append(f"{digest}  {path}")

    MANIFEST_PATH.write_text("\n".join(lines) + "\n")


def load_manifest() -> dict:
    """Load manifest from file. Returns {relative_path: hash}."""
    if not MANIFEST_PATH.exists():
        return {}

    manifest = {}
    for line in MANIFEST_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("  ", 1)
        if len(parts) == 2:
            digest, path = parts
            manifest[path] = digest
    return manifest


# ── Validation ─────────────────────────────────────────────────────────────────

def validate() -> tuple[bool, list[str]]:
    """
    Check all governed files against the manifest.
    Returns (all_ok, list_of_violations).
    """
    violations = []

    if not MANIFEST_PATH.exists():
        violations.append(
            "CRITICAL: hash_manifest.txt not found — governance layer not initialised. "
            "Run: python governance/validator.py --rehash"
        )
        return False, violations

    recorded = load_manifest()

    for rel in GOVERNED_FILES:
        p = BASE_DIR / rel

        # File missing
        if not p.exists():
            violations.append(f"MISSING: {rel}")
            continue

        # Not in manifest
        if rel not in recorded:
            violations.append(f"NOT IN MANIFEST: {rel} — run --rehash after intentional edits")
            continue

        # Hash mismatch
        current = sha256(p)
        if current != recorded[rel]:
            violations.append(
                f"TAMPERED: {rel}\n"
                f"  expected: {recorded[rel]}\n"
                f"  got:      {current}"
            )

    return len(violations) == 0, violations


# ── CLI ────────────────────────────────────────────────────────────────────────

def cmd_check(hard_stop: bool = True):
    """Run validation. Hard stop on failure if hard_stop=True."""
    print("\n── Zion Governance Validator ─────────────────────────────────────")

    ok, violations = validate()

    if ok:
        manifest = load_manifest()
        print(f"  OK  All {len(manifest)} governed files verified")
        print("─────────────────────────────────────────────────────────────────\n")
        return True
    else:
        print(f"\n  !! GOVERNANCE VIOLATION — {len(violations)} issue(s) found:\n")
        for v in violations:
            for line in v.splitlines():
                print(f"     {line}")
        print()

        if hard_stop:
            print("  HARD STOP — Zion will not start with tampered governance files.")
            print("  To fix:")
            print("    - If you made intentional changes: python governance/validator.py --rehash")
            print("    - If you did not change these files: investigate before proceeding")
            print("─────────────────────────────────────────────────────────────────\n")
            sys.exit(1)
        else:
            print("─────────────────────────────────────────────────────────────────\n")
            return False


def cmd_rehash():
    """Rebuild the hash manifest from current file state."""
    print("\n── Zion Governance Validator — Rehash ────────────────────────────")

    manifest = build_manifest()
    save_manifest(manifest)

    print(f"  Hashed {len(manifest)} files:")
    for path, digest in sorted(manifest.items()):
        print(f"    {digest[:16]}…  {path}")

    print(f"\n  Manifest saved to: governance/hash_manifest.txt")
    print("─────────────────────────────────────────────────────────────────\n")


# ── Importable boot check (called from app.py) ─────────────────────────────────

def boot_check():
    """
    Call this from app.py at startup.
    Exits the process if governance files have been tampered with.
    """
    cmd_check(hard_stop=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zion Governance Validator")
    parser.add_argument("--rehash",  action="store_true", help="Rebuild hash manifest")
    parser.add_argument("--status",  action="store_true", help="Check status without hard stop")
    args = parser.parse_args()

    if args.rehash:
        cmd_rehash()
    elif args.status:
        cmd_check(hard_stop=False)
    else:
        cmd_check(hard_stop=True)
