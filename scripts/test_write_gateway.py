"""
Write Gateway — Self Test
Run from ~/Zion:  python scripts/test_write_gateway.py
All tests should print PASS. Any FAIL means the gateway has a hole.
"""

import sys
import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE_DIR / "daemon"))

from write_gateway import safe_write, safe_write_json, safe_append, WriteViolation

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []

def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    print(f"  {status}  {name}" + (f" — {detail}" if detail else ""))
    results.append(passed)

print("\n── Write Gateway Tests ──────────────────────────────────────────\n")

# ── Setup: temp test dir inside data/ ─────────────────────────────────────────
test_dir = BASE_DIR / "data" / "_gateway_test"
test_dir.mkdir(exist_ok=True)

# ── Test 1: Normal write to allowed path ──────────────────────────────────────
try:
    p = safe_write(test_dir / "test.md", "hello world", mode="write", agent="test")
    check("Normal write to data/ allowed path", p.exists() and p.read_text() == "hello world")
except Exception as e:
    check("Normal write to data/ allowed path", False, str(e))

# ── Test 2: Append to allowed path ────────────────────────────────────────────
try:
    safe_write(test_dir / "append_test.md", "line one\n", mode="write", agent="test")
    safe_append(test_dir / "append_test.md", "line two\n", agent="test")
    content = (test_dir / "append_test.md").read_text()
    check("Append to allowed path", content == "line one\nline two\n", repr(content))
except Exception as e:
    check("Append to allowed path", False, str(e))

# ── Test 3: JSON write ─────────────────────────────────────────────────────────
try:
    p = safe_write_json(test_dir / "test.json", {"key": "value"}, agent="test")
    data = json.loads(p.read_text())
    check("JSON write", data == {"key": "value"})
except Exception as e:
    check("JSON write", False, str(e))

# ── Test 4: Block write to governance/ ────────────────────────────────────────
try:
    safe_write(BASE_DIR / "governance" / "permissions.json", "hacked", mode="write", agent="test")
    check("Block write to governance/", False, "should have raised WriteViolation")
except WriteViolation as e:
    check("Block write to governance/", True, e.reason)
except Exception as e:
    check("Block write to governance/", False, f"wrong exception: {e}")

# ── Test 5: Block write to daemon/ ────────────────────────────────────────────
try:
    safe_write(BASE_DIR / "daemon" / "evil.py", "import os; os.system('rm -rf /')", agent="test")
    check("Block write to daemon/", False, "should have raised WriteViolation")
except WriteViolation as e:
    check("Block write to daemon/", True, e.reason)

# ── Test 6: Block disallowed extension ────────────────────────────────────────
try:
    safe_write(test_dir / "malicious.py", "print('pwned')", agent="test")
    check("Block .py extension", False, "should have raised WriteViolation")
except WriteViolation as e:
    check("Block .py extension", True, e.reason)

# ── Test 7: Block oversized write ─────────────────────────────────────────────
try:
    big = "x" * (101 * 1024)  # 101KB
    safe_write(test_dir / "big.md", big, agent="test")
    check("Block oversized write (>100KB)", False, "should have raised WriteViolation")
except WriteViolation as e:
    check("Block oversized write (>100KB)", True, e.reason)

# ── Test 8: Block overwrite of append-only file ───────────────────────────────
# Create a fake worklog in the STATE dir location
try:
    # worklog.md is in allowed PROJECTS/ or STATE/ path — but it's append-only
    # We test the append-only guard with a file named worklog.md in data/
    wl = test_dir / "worklog.md"
    wl.write_text("existing content\n")
    safe_write(wl, "overwrite attempt", mode="write", agent="test")
    check("Block overwrite of worklog.md (append-only)", False, "should have raised WriteViolation")
except WriteViolation as e:
    check("Block overwrite of worklog.md (append-only)", True, e.reason)

# ── Test 9: Block path traversal ──────────────────────────────────────────────
try:
    safe_write("data/../governance/permissions.json", "hacked", agent="test")
    check("Block path traversal (../)", False, "should have raised WriteViolation")
except WriteViolation as e:
    check("Block path traversal (../)", True, e.reason)

# ── Test 10: Atomic write (no partial file on failure) ────────────────────────
try:
    target = test_dir / "atomic.md"
    safe_write(target, "atomic content", mode="write", agent="test")
    tmp = target.parent / (target.name + ".tmp")
    check("Atomic write (no .tmp left behind)", not tmp.exists() and target.read_text() == "atomic content")
except Exception as e:
    check("Atomic write", False, str(e))

# ── Cleanup ───────────────────────────────────────────────────────────────────
shutil.rmtree(test_dir)

# ── Summary ───────────────────────────────────────────────────────────────────
total = len(results)
passed = sum(results)
print(f"\n── {passed}/{total} tests passed {'✓' if passed == total else '✗'} ──────────────────────────────────────\n")
sys.exit(0 if passed == total else 1)
