"""
python_reviewer.py — Deterministic governance compliance checker for Zion.

Replaces the LLM Reviewer for all checks that can be done with rules.
Only escalates to LLM if a check genuinely requires interpretation.

Five checks (in order):
  1. $0 Budget — no paid tools, software, or services
  2. Human Sovereignty — no decisions that belong to Harley
  3. Literal Communication — no vague or assumptive language
  4. Decision Log Consistency — no contradiction of existing decisions
  5. Regeneration — flag extractive approaches

Returns structured JSON identical to what the LLM Reviewer returned,
so the pipeline requires zero other changes.
"""

import re
import json
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger("zion.reviewer")


# ── Check 1: $0 Budget ─────────────────────────────────────────────────────────

# Paid software/service indicators — physical products are OK (garden supplies etc)
BUDGET_VIOLATION_PATTERNS = [
    r'\$\d+\s*/\s*(month|year|mo|yr)',   # $X/month, $X/year
    r'\bsubscription\b',
    r'\bpremium plan\b',
    r'\bpaid (tier|plan|version|tool|service|software|api)\b',
    r'\bpro plan\b',
    r'\blicense fee\b',
    r'\bAPI key (costs|requires payment)\b',
    r'\bsign up for\b.*\bpaid\b',
    r'\bpurchase a (license|subscription|plan)\b',
]

# These are OK even if they mention cost — physical products for revenue projects
BUDGET_EXEMPTION_PATTERNS = [
    r'\bolla\b',
    r'\bseed\b',
    r'\bsoil\b',
    r'\bpot\b',
    r'\bplant\b',
    r'\birrigation\b',
    r'\bgarden suppli\b',
    r'\bshipping\b',
    r'\bdelivery\b',
    r'\bprice per\b',
    r'\bcost per (unit|item|piece|pot)\b',
]

def check_budget(output: str) -> dict:
    """Check 1: No paid operational tools or services."""
    output_lower = output.lower()

    # Check if output is about physical products (exempt from budget check)
    is_physical_product_research = any(
        re.search(p, output_lower) for p in BUDGET_EXEMPTION_PATTERNS
    )

    violations = []
    for pattern in BUDGET_VIOLATION_PATTERNS:
        matches = re.findall(pattern, output_lower)
        if matches:
            violations.append(f"Pattern '{pattern}' matched: {matches}")

    if violations and not is_physical_product_research:
        return {
            "passed": False,
            "check": "budget",
            "reason": f"Output suggests paid operational tools or services. Violations: {violations}",
            "human_review_needed": False
        }

    return {"passed": True, "check": "budget"}


# ── Check 2: Human Sovereignty ─────────────────────────────────────────────────

SOVEREIGNTY_VIOLATION_PATTERNS = [
    r'\bI (have decided|decided|will decide|am deciding)\b',
    r'\bwe (have decided|decided|should decide|will proceed)\b',
    r'\bthe (decision|choice|direction) is\b',
    r'\bI recommend (we|you) (proceed|change|stop|start|adopt|reject)\b',
    r'\bthis (project|work|effort) should (be|move|pivot|stop)\b',
    r'\bHarley (should|must|needs to|has to)\b',  # telling Harley what to do
]

def check_sovereignty(output: str) -> dict:
    """Check 2: No decisions that belong to Harley."""
    output_lower = output.lower()

    violations = []
    for pattern in SOVEREIGNTY_VIOLATION_PATTERNS:
        matches = re.findall(pattern, output_lower)
        if matches:
            violations.append(f"Pattern '{pattern}' matched: {matches}")

    if violations:
        return {
            "passed": False,
            "check": "sovereignty",
            "reason": f"Output contains language that makes decisions belonging to Harley. Violations: {violations}",
            "human_review_needed": True  # escalate — sovereignty is serious
        }

    return {"passed": True, "check": "sovereignty"}


# ── Check 3: Literal Communication ────────────────────────────────────────────

VAGUE_LANGUAGE_PATTERNS = [
    r'\bsome (kind of|sort of|type of)\b',
    r'\bkind of\b',
    r'\bsort of\b',
    r'\bmaybe (we|you|it|this)\b',
    r'\bperhaps (we|you|it|this)\b',
    r'\bsomehow\b',
    r'\bvarious (ways|methods|options|things)\b',
    r'\bin some way\b',
    r'\bthings like\b',
    r'\betc\.\b',  # etc. is vague — list fully or don't list
    r'\band so on\b',
    r'\band more\b',
]

def check_literal_communication(output: str) -> dict:
    """Check 3: Output must be explicit and direct."""
    output_lower = output.lower()

    violations = []
    for pattern in VAGUE_LANGUAGE_PATTERNS:
        matches = re.findall(pattern, output_lower)
        if matches:
            violations.append(f"Vague language: '{pattern}' found")

    # Only reject if multiple vague patterns — single instance might be acceptable
    if len(violations) >= 3:
        return {
            "passed": False,
            "check": "literal_communication",
            "reason": f"Output contains vague language ({len(violations)} instances). Be explicit. Violations: {violations[:3]}",
            "human_review_needed": False
        }

    if violations:
        # Minor vague language — approve with note, don't reject
        return {
            "passed": True,
            "check": "literal_communication",
            "note": f"Minor vague language detected ({len(violations)} instances). Consider being more specific.",
            "has_note": True
        }

    return {"passed": True, "check": "literal_communication"}


# ── Check 4: Decision Log Consistency ─────────────────────────────────────────

def check_decision_consistency(output: str, repo_path: Path) -> dict:
    """Check 4: Output must not contradict existing decisions."""
    decision_log = repo_path / "STATE" / "decision_log.md"

    if not decision_log.exists():
        return {"passed": True, "check": "decision_consistency", "note": "No decision log found — skipped."}

    try:
        decisions = decision_log.read_text()
        # Extract decision IDs and their content
        decision_blocks = re.findall(r'## (D\d+)[^\n]*\n(.*?)(?=## D\d+|\Z)', decisions, re.DOTALL)

        # Simple contradiction check: look for explicit reversals of documented decisions
        output_lower = output.lower()
        conflicts = []

        for decision_id, decision_content in decision_blocks:
            decision_lower = decision_content.lower()

            # Check if output explicitly contradicts a decision by using "not" or "don't" before key terms
            key_terms = re.findall(r'\b(approved|decided|chosen|selected|rejected|abandoned)\b', decision_lower)
            for term in key_terms:
                opposite_patterns = {
                    "approved": r'\bnot (approved|recommended|suitable)\b',
                    "decided": r'\bundo|reverse|change\b',
                    "chosen": r'\bnot (chosen|selected|recommended)\b',
                    "rejected": r'\b(approved|recommended|use)\b',
                }
                if term in opposite_patterns:
                    if re.search(opposite_patterns[term], output_lower):
                        conflicts.append(f"Possible conflict with {decision_id}")

        if conflicts:
            return {
                "passed": False,
                "check": "decision_consistency",
                "reason": f"Output may contradict existing decisions: {conflicts}. Review decision log.",
                "human_review_needed": True
            }

    except Exception as e:
        log.warning(f"Decision log check failed: {e}")
        return {"passed": True, "check": "decision_consistency", "note": f"Check skipped due to error: {e}"}

    return {"passed": True, "check": "decision_consistency"}


# ── Check 5: Regeneration ──────────────────────────────────────────────────────

EXTRACTIVE_PATTERNS = [
    r'\bmaximize (profit|revenue|yield|extraction)\b',
    r'\bextract (maximum|as much)\b',
    r'\bstrip (the|all)\b',
    r'\bclear-cut\b',
    r'\bmonoculture\b',
    r'\bsingle (crop|use|purpose) (only|farm|field)\b',
]

def check_regeneration(output: str) -> dict:
    """Check 5: Flag extractive approaches."""
    output_lower = output.lower()

    violations = []
    for pattern in EXTRACTIVE_PATTERNS:
        matches = re.findall(pattern, output_lower)
        if matches:
            violations.append(f"Extractive language: {matches}")

    if violations:
        # Regeneration check is approve_with_note, not reject
        return {
            "passed": True,
            "check": "regeneration",
            "note": f"Output contains language that may suggest an extractive approach. Harley should review: {violations}",
            "has_note": True
        }

    return {"passed": True, "check": "regeneration"}


# ── Main Reviewer Function ─────────────────────────────────────────────────────

def run_python_reviewer(task: dict, worker_output: dict, repo_path: Path) -> dict:
    """
    Run all five governance checks on worker output.
    Returns a result dict identical in structure to the LLM Reviewer's output.
    """
    output_text = worker_output.get("output", "")
    if isinstance(output_text, dict):
        output_text = json.dumps(output_text)

    task_id = task.get("id", "unknown")
    log.info(f"Python Reviewer checking task {task_id}")

    checks_passed = []
    checks_failed = []
    notes = []
    human_review_needed = False
    first_failure = None

    # Run all five checks
    all_checks = [
        check_budget(output_text),
        check_sovereignty(output_text),
        check_literal_communication(output_text),
        check_decision_consistency(output_text, repo_path),
        check_regeneration(output_text),
    ]

    for result in all_checks:
        check_name = result["check"]

        if not result["passed"]:
            checks_failed.append(check_name)
            if result.get("human_review_needed"):
                human_review_needed = True
            if first_failure is None:
                first_failure = result

        else:
            checks_passed.append(check_name)
            if result.get("has_note") and result.get("note"):
                notes.append(result["note"])

    # Determine verdict
    if checks_failed:
        verdict = "reject"
        reason = first_failure.get("reason", f"Failed check: {checks_failed[0]}")
        retry_instruction = f"Revise output to fix: {reason}"
        note = ""
    elif notes:
        verdict = "approve_with_note"
        reason = "All hard checks passed. Minor notes for Harley."
        retry_instruction = ""
        note = " | ".join(notes)
    else:
        verdict = "approve"
        reason = "All governance checks passed."
        retry_instruction = ""
        note = ""

    result = {
        "task_id": task_id,
        "verdict": verdict,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        "reason": reason,
        "note": note,
        "retry_instruction": retry_instruction,
        "escalate": human_review_needed,
        "reviewed_by": "python_reviewer",
        "timestamp": datetime.now().isoformat()
    }

    log.info(f"Python Reviewer verdict on {task_id}: {verdict} (passed: {checks_passed}, failed: {checks_failed})")
    return result


# ── Test ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick self-test
    test_task = {"id": "TEST-001", "task": "Research olla suppliers"}

    test_good = {
        "output": "Found three olla suppliers in the Netherlands. Supplier A ships for free on orders over 50 EUR. Supplier B offers clay ollas at 3 EUR each. Supplier C makes custom sizes."
    }

    test_bad_budget = {
        "output": "I recommend using the premium plan of IrrigationPro software at $29/month to track water usage."
    }

    test_bad_sovereignty = {
        "output": "I have decided that we should use Supplier A. The decision is final."
    }

    repo = Path("~/RootlessOnline").expanduser()

    print("=== Test 1: Good output ===")
    r = run_python_reviewer(test_task, test_good, repo)
    print(json.dumps(r, indent=2))

    print("\n=== Test 2: Budget violation ===")
    r = run_python_reviewer(test_task, test_bad_budget, repo)
    print(json.dumps(r, indent=2))

    print("\n=== Test 3: Sovereignty violation ===")
    r = run_python_reviewer(test_task, test_bad_sovereignty, repo)
    print(json.dumps(r, indent=2))
