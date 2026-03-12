#!/bin/bash
# Clean Z from RootlessOnline repo and restructure for Zion
# Run this from inside your RootlessOnline folder

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Restructuring RootlessOnline for Zion   ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if [ ! -f "START.md" ]; then
  echo "✗ Run this from inside your RootlessOnline repo folder"
  exit 1
fi

# ── Update START.md ─────────────────────────────────────
cat > START.md << 'EOF'
# START.md — First File Any AI Reads

> **READ THIS FILE FIRST.**

---

## What Is The Collective?

The Collective is a **regenerative civic network** building local communities through:
1. **Garden Business** — Olla irrigation, permaculture, therapeutic horticulture
2. **Collective Hub** — Platform and tools for community coordination
3. **Community Tools** — Tool library, neighborhood connection
4. **Political Party** — Netherlands-based, 4-year deadline

**Founded by:** Harley (CEO) — Human, autistic, $0 budget, literal communication style, she/her

---

## AI Coordination

All AI coordination happens through **Zion** — the local cockpit at https://github.com/RootlessOnline/Zion

Zion runs locally on Harley's machine and manages:
- Manager agent (central coordinator)
- Worker agent (task execution)
- Reviewer agent (governance checking)
- Logger agent (repo writes)
- Watcher agent (history and efficiency monitoring)

**This repo is the project.** Zion is the cockpit that coordinates work on it.

---

## Who's Who

| Role | Name | Responsibility |
|------|------|----------------|
| CEO | Harley (she/her) | Human founder. Final authority. Literal communicator. |
| Cockpit | Zion | Local AI coordination system |

---

## How AIs Work Here

1. Read CONSTITUTION.md — immutable principles
2. Read BYLAWS.md — operational rules
3. Read STATE/current_state.md — what's happening now
4. Read STATE/decision_log.md — previous decisions
5. Document everything with provenance tags
6. Escalate to Harley for principle-level decisions

---

## Quick Rules

1. **Harley is literal** — No subtext, no hints, no assumptions (she/her)
2. **$0 budget** — All solutions must be free or revenue-generating
3. **Transparency** — Everything documented, nothing hidden
4. **Regenerative** — Build soil, community, and capacity
5. **Human sovereignty** — Harley decides, AIs assist

---

## File Structure

```
RootlessOnline/
├── START.md           ← You are here
├── CONSTITUTION.md    — Purpose + Principles (immutable)
├── BYLAWS.md          — Operational rules
├── OVERVIEW.md        — One-page summary
├── TASKS.md           — All tasks across all projects
├── STATE/             — current_state.md, decision_log.md, worklog.md
├── PROJECTS/          — garden_business, collective_hub, desert_restoration, political_party
└── RESEARCH/          — Raw findings
```
EOF
echo "✓ START.md updated"

# ── Update AI_BOM.md ────────────────────────────────────
cat > AI_BOM.md << 'EOF'
# AI_BOM.md — AI Bill of Materials

> Inventory of all AI systems working with The Collective.
> Coordination is managed through Zion: https://github.com/RootlessOnline/Zion

---

## Active AI Systems

### Cockpit: Zion

| Property | Value |
|----------|-------|
| **Name** | Zion |
| **Role** | Local AI cockpit — coordinates all agents |
| **Repo** | https://github.com/RootlessOnline/Zion |
| **Runs on** | Harley's local machine |
| **Model** | Gemma 3 12B via Ollama |
| **Status** | Active |

**Agents inside Zion:**
- Manager — central coordinator, talks to Harley
- Worker — executes tasks
- Reviewer — governance compliance checking
- Logger — writes approved outputs to this repo
- Watcher — monitors history and efficiency

---

## Retired AI Systems

| Name | Role | Reason retired |
|------|------|----------------|
| Z | Manager AI | Replaced by Zion cockpit |
| ChatGPT Architect | Architecture | Replaced by Zion Manager agent |

---
EOF
echo "✓ AI_BOM.md updated"

# ── Update PERMISSIONS.yaml ─────────────────────────────
cat > PERMISSIONS.yaml << 'EOF'
# PERMISSIONS.yaml
# All AI coordination is handled by Zion (https://github.com/RootlessOnline/Zion)

zion_cockpit:
  read:
    - all_files
  write:
    - STATE/worklog.md
    - STATE/decision_log.md
    - STATE/current_state.md
    - TASKS.md
  git:
    - commit: false      # Harley commits manually or via Zion sync button
    - push: false        # Harley pushes manually or via Zion sync button
    - pull: true

harley:
  read:
    - all_files
  write:
    - all_files
  git:
    - all_operations: true
EOF
echo "✓ PERMISSIONS.yaml updated"

# ── Remove old AI_SYSTEM files that reference Z ─────────
if [ -f "AI_SYSTEM/boot_sequence.md" ]; then
  sed -i 's/Z (Manager AI)/Zion cockpit/g' AI_SYSTEM/boot_sequence.md
  sed -i 's/Manager AI: Z/Cockpit: Zion/g' AI_SYSTEM/boot_sequence.md
  echo "✓ AI_SYSTEM/boot_sequence.md updated"
fi

if [ -f "AI_SYSTEM/conflict_playbook.md" ]; then
  sed -i 's/Z handles/Zion Manager handles/g' AI_SYSTEM/conflict_playbook.md
  sed -i 's/Escalate to Z/Escalate to Harley via Zion/g' AI_SYSTEM/conflict_playbook.md
  echo "✓ AI_SYSTEM/conflict_playbook.md updated"
fi

# ── Add ZION.md reference file ──────────────────────────
cat > ZION.md << 'EOF'
# ZION.md — The Cockpit

Zion is the local AI UI system that coordinates all work on The Collective.

**Repo:** https://github.com/RootlessOnline/Zion
**Runs at:** http://localhost:5000 (on Harley's machine)

## What Zion Does

- Coordinates AI agents working on this project
- Lets Harley manage tasks, switch projects, and get briefings
- Writes approved outputs to this repo via the Logger agent
- Monitors agent efficiency via the Watcher agent
- Keeps working when Harley is away, briefing her when she returns

## Connection to This Repo

Zion reads from and writes to this repo via local clone.
Harley syncs changes to GitHub via Zion's sync button.

Zion does NOT live inside this repo. It lives at:
https://github.com/RootlessOnline/Zion
EOF
echo "✓ ZION.md created"

# ── Commit changes ──────────────────────────────────────
echo ""
echo "▶ Committing changes..."
git add .
git commit -m "Remove Z, restructure for Zion cockpit coordination"
git push origin main

echo ""
echo "✓ RootlessOnline repo restructured."
echo ""
echo "Z has been removed. Zion is now the coordination layer."
echo ""
