# Zion

> The cockpit. Lives outside the Matrix. Controls everything inside it.

Zion is the local AI command centre for [The Collective](https://github.com/RootlessOnline/RootlessOnline). It runs entirely on your machine, connects to your project repo, and coordinates multiple AI agents that work with you — and without you.

---

## What Zion Does

- **Shows all agents** on screen with live status — what they just did, what they're doing, what's next
- **Manager chat** in the centre — you talk to Manager, Manager coordinates agents, brings results back to you
- **Watcher** monitors everything silently — efficiency, history, patterns — and reflects with you when you want
- **Works while you're away** — agents keep working, you get a briefing when you return
- **Emergency stop** — freeze everything, correct course, resume
- **Project switcher** — switch between all Collective projects instantly
- **Version control panel** — sync to GitHub with one button, no terminal git commands needed

---

## Hardware Requirements

| Component | Minimum | Harley's Setup |
|-----------|---------|----------------|
| GPU VRAM | 8GB | 12GB ✅ |
| RAM | 16GB | 32GB ✅ |
| OS | Linux | Ubuntu + Cinnamon ✅ |
| CUDA | 11.x | 12.2 ✅ |

---

## Quick Start

```bash
# 1. Clone Zion
git clone https://github.com/RootlessOnline/Zion.git
cd Zion

# 2. Run setup (installs everything)
chmod +x scripts/setup.sh
./scripts/setup.sh

# 3. Configure your project repo path
nano config.json

# 4. Start Zion
./scripts/start.sh
```

Then open `http://localhost:5000` — Zion is running.

---

## Architecture

```
Zion/
├── dashboard/          ← The UI (Flask + vanilla JS)
├── daemon/             ← Scheduler + agent pipeline
├── agents/             ← Coordinator, Worker, Reviewer, Logger, Watcher
├── prompts/            ← System prompts for each agent role
├── data/               ← task_queue, session_state, briefings
├── scripts/            ← setup.sh, start.sh, stop.sh
└── docs/               ← Architecture docs
```

---

## The Agents

| Agent | Role | Works When |
|-------|------|-----------|
| Manager | Central coordinator, talks to Harley | Always |
| Worker | Does the actual project tasks | Away mode |
| Reviewer | Checks outputs against CONSTITUTION | Away mode |
| Logger | Writes approved outputs to repo files | Away mode |
| Watcher | Monitors all agents, keeps history | Always |

---

## Connected Repos

- **The Collective:** `https://github.com/RootlessOnline/RootlessOnline` — project lives here
- **Zion:** `https://github.com/RootlessOnline/Zion` — cockpit lives here

---

*Zion exists outside the Matrix. That's the point.*
