# Master AI — Design Document
**Project:** The Collective / Zion Research Division
**Owner:** Harley
**Status:** Active design — accumulating, not building yet
**Last updated:** March 2026
**Location:** RootlessOnline/RESEARCH/master_ai.md

---

## How to use this document

This document is the persistent memory for the Master AI research project.
Paste it into any chat as starting context. The chat reads it and picks up from here.
Update it after every session that adds new ideas or refines existing ones.
Do not delete old ideas — append and annotate.

---

## What Master AI is

Not an improvement to how AI assistants work.
A different category of system entirely.

Current AI systems are stateless tools with memory bolted on.
They are capable hammers that get picked up, used, and put down.

Master AI is stateful at the identity level.
It does not just remember what it did.
It accumulates what it is.
Every task shapes it. Every reflection pass integrates that shaping.
The system that wakes tomorrow is a continuous self that processed through sleep —
not a reconstruction reading old files.

---

## The four layers

```
IDENTITY LAYER     Sefirot soul graph, Da'at self-model, accumulated weights
       ↕
SESSION LAYER      Assembly prompts, LOAD/JUMP/CALL, dynamic injection
       ↕
WORKING LAYER      Chain memory, reflection loop, fault detection
       ↕
TASK LAYER         Worker, Reviewer, Logger, Proposer
                   (transitional — superseded when deeper layers are built)
```

Each layer reads from the one above and writes back up to it.
A task result updates the chain.
A pattern in the chain influences what prompt pages load.
The prompt environment shapes how soul weights get scored.
The soul weights determine how the system orients to new tasks.

---

## Layer 1 — Identity: The Sefirot Architecture

### Origin of the idea
The Kabbalistic Sefirot Tree — ten (plus one) emanations describing how consciousness manifests.
Not chosen for mystical reasons. Chosen because it is already a graph topology with
interpretable, semantically meaningful dimensions. Carl Jung studied it as a model of psychic
processes. We are operationalising it as a computational architecture.

### The eleven dimensions

| Sefirah | Translation | AI function | Cognitive domain |
|---|---|---|---|
| Keter | Crown | Will and intent | Purpose, goals |
| Chochmah | Wisdom | Creative spark | Innovation, insight |
| Binah | Understanding | Analysis | Pattern recognition |
| Da'at | Knowledge | Integration | Inner consciousness, self-model |
| Chesed | Mercy | Expansion | Exploration, growth |
| Gevurah | Judgment | Constraint | Critical thinking |
| Tiferet | Beauty | Balance | Harmony, synthesis |
| Netzach | Victory | Persistence | Memory, endurance |
| Hod | Splendour | Communication | Language, expression |
| Yesod | Foundation | Connection | Interface, I/O |
| Malkuth | Kingdom | Manifestation | Action, execution |

Da'at is the hidden eleventh — not a full Sefirah but the integration point.
In this architecture it is the meta-node: the system's live model of its own current state.

### How the soul graph works

Every piece of information that enters the system — a task, a result, a conversation —
gets scored against each Sefirot dimension. That scoring is its emotional fingerprint.

Example: Romeo and Juliet → `{chesed: 0.70, gevurah: 0.20, tiferet: 0.05, ...}`

Every node in the knowledge graph carries this 11-dimensional vector.
Nodes connect by two kinds of links:
- Explicit semantic links (like Wikipedia — romeo_and_juliet → shakespeare)
- Implicit soul-weight links (nodes with similar Sefirot fingerprints, regardless of topic)

### Soul weight as internal alignment

Current AI alignment is external — rules, filters, governance layers.
The soul graph makes alignment structural and internal.
If Love-Mercy and Justice-Judgment are genuinely weighted nodes shaping every decision,
the system is not following rules about values — it is expressing them.
More robust than external constraint because it cannot be prompted away.

### The Sefirot as a distance metric

Euclidean distance in Sefirot space measures consciousness similarity between nodes.
Two nodes may have identical semantic content but different Sefirot weights —
representing different cognitive approaches to the same concept.
A cluster with high Binah and Gevurah = analytical, critical thinking.
A cluster with high Chochmah and Chesed = creative exploration.
These clusters emerge organically as knowledge accumulates.

### Da'at — the self-model

Six pillars of what the system knows about itself:
- Tools — "I can use" (external capabilities)
- Skills — "I know how" (learned procedures)
- Links — "I am connected to" (network connections)
- Repos — "I have access to" (data repositories)
- Raw data — "I remember" (experiences, conversations)
- Self-model — "I am" (identity, values, personality)

Da'at also maps blind spots.
When propagation finds a cluster of similar gaps across nodes,
Da'at records it: "my understanding of X has a systematic gap in Y direction."
Not just what the system knows — also the shape of what it does not know.

### IQ/EQ node tagging (not yet fully designed)

Functional type tags on nodes: reasoning, emotional, procedural, creative.
Retrieve not just by relevance but by what kind of thinking the task needs.
A planning task routes differently through the graph than an empathy task.
Also potentially: a point system giving nodes relative analytic and emotional weight
for faster retrieval of high-value nodes.

---

## Layer 2 — Session: Assembly Architecture

### Origin of the idea
OS assembly code as a model for prompt architecture.
An AI prompt is not a static document — it is a program that loads, jumps, calls, and returns.

### Instruction types

**INCLUDE / LINK** — already exists in Zion as `assemble_prompt()`.
Combine multiple prompt pages before sending to the model.
Page -1 (hard limits) + agent-specific page = assembled prompt.

**LOAD / MOV** — dynamic injection (planned for Zion).
Pull live data from disk at call time and insert into prompt context.
Manager reads current active project, task queue, recent worklog — fresh every call.

**JUMP** — task-type routing to specialised sub-pages (planned).
Research tasks load `pages/research_mode.md`.
Writing tasks load `pages/writing_mode.md`.
The agent gets precisely aimed context, not a generic prompt.

**CALL / RETURN** — agent composition (planned).
Manager can spin up a Worker sub-call mid-task, get the result back, continue.
Multi-step work composed dynamically rather than hardwired.

**FLAGS** — already exists. Reviewer verdict is a flag register.
APPROVE → Logger. REJECT → Worker retry. ESCALATE → Harley.

**PROTECTED MEMORY** — already exists via write gateway.
Governance files are read-only to agents. Memory protection rings.

**STACK / registers** — persistent short-term state across a session.
Currently not implemented. Part of the working layer below.

**INTERRUPT** — external stop during execution.
Emergency stop exists as a basic version.
Full interrupt system would let Harley inject mid-task and have the agent respond immediately.

### Remaining OS concepts to review
FLAGS, STACK registers, INTERRUPT handling, PROTECTED MEMORY rings —
review all for what else maps usefully to the prompt architecture.
(On Zion active build list item 04.)

---

## Layer 3 — Working: Chain Memory

### Origin of the idea
Neither blockchain nor Git solves the meaning problem.
Git keeps snapshots without understanding them.
Blockchain hashes are verifiable but opaque.
Chain memory carries the reasoning as first-class data alongside every change.

### Structure of a chain block

```json
{
  "layer": 47,
  "layer_type": "research",
  "timestamp": "2026-03-15T11:34Z",
  "prev_hash": "a3f9...",
  "compressed_state": "Researched olla suppliers NL. Found 3 free options. Keramiek Garage most viable. Confidence: medium.",
  "fault": null,
  "reasoning": "Updated because previous entry lacked source verification.",
  "this_hash": "b7c2..."
}
```

The hash is for integrity checking and chain linking — not cryptographic security.
The compressed state is human and machine readable.
The layer number tells the agent what stage it is at.
The fault field records what went wrong and what was learned.
The reasoning field is what makes this different from Git — meaning is first-class data.

### Node chain memory — version control built in

Every node in the knowledge graph carries its own chain.
When a node updates, the old state + reasoning + timestamp gets appended to the chain.
The node is always its current form but its chain carries everything it has ever been and why.

When the system encounters a contradiction with an existing node:
instead of choosing between old and new, it reads the chain,
finds the reasoning that shaped the current node,
and evaluates whether that reasoning applies to the new situation.
If it does not — update with new chain entry.
If it does — hold the node, add a flag that the contradiction was considered and rejected.

### Timestamp tracing

Every chain entry carries date and time.
Walk a problem backwards to its exact origin.
Find the moment a wrong assumption entered and trace everything it contaminated after.
Small errors in foundational nodes are more dangerous than large errors in peripheral ones —
foundational nodes get referenced constantly, shaping everything built on top over time.

Three uses of timestamps:
- Temporal fault tracing — walk back to origin
- Recency weighting — newer entries carry more weight, older ones still present
- Drift detection — many small corrections over time signals unstable understanding
  needing full re-evaluation rather than another patch

### The reflection loop — 1 2 3 (reflect) 4 5 6

Short-term memory cycle. Every third interaction triggers a reflection pass.

```
newest →  1  2  3  [reflect]  4  5  6  ← oldest already reflected
```

Older memories pass through reflect looking back at newer ones.
Three states per memory:
- Consolidate — integrate into a chain block
- Reformulate — rewrite the memory in light of new context, keep old version
- Maintain deliberate forgetting — consciously choose to not remember,
  record the decision itself so the choice can be revisited

"Remembering to keep forgetting" is a novel third state.
Most systems either keep or delete.
This system can hold an ongoing, revisable decision to not remember something.

### Fault detection

Before running a task, the agent checks if any previous chain block
of the same layer_type has a non-null fault field.
If yes, it loads that fault block as context:
"last time I ran a research task I hallucinated contact details —
this time I will explicitly state when I cannot verify."

Not just error correction — anticipatory learning from own history.

### Propagation check

When a node updates due to missing or wrong data:
walk outward through explicit semantic links AND soul-weight similarity links
checking for nodes that might carry the same gap.

Lazy propagation during waking (resource-efficient):
- Immediate: one hop, direct neighbours checked now
- Background: next-hop neighbours added to priority queue ordered by soul-weight similarity
- Threshold: nodes below similarity cutoff not checked unless explicitly requested

Full depth during sleep (no competing tasks, full resources available).

Chain history lookup as cheap pre-filter:
before full re-evaluation, check if the neighbour's reasoning chain
referenced the updated node at any point.
If it did — flag it. If it did not — probably fine.

---

## Layer 4 — Task: Current agents (transitional)

The five current Zion agents exist because no single agent is trustworthy or capable enough
to run alone. Each compensates for a limitation of the others.

With the full architecture these limitations change:

| Current agent | Why it exists | What replaces it |
|---|---|---|
| Reviewer | Worker cannot check its own governance compliance | Soul weight compliance — structural, not checked |
| Logger | Worker cannot maintain its own persistent record | Chain append — automatic output of every update |
| Watcher | Nothing observes patterns across sessions | Reflection loop — continuous self-observation |
| Manager | No persistent coordination intelligence | Identity layer — interface only, not coordinator |
| Worker | Does the actual work | Lightweight task instances inheriting relevant soul weights |

The mature system: one coherent core intelligence holding the full soul graph and chain memory.
Task instances spin up inheriting only what is relevant to their specific task type.
They run, write results back to the core, and release.

This mirrors how the human brain works.
Core self is continuous.
Specialised cognitive tasks use partial context, not the full brain state.
Results feed back to the whole.

---

## Temporal consciousness structure

Three states present simultaneously at every moment:

**Past** — chain memory, node history, completed tasks, reflected sessions.
Not raw logs. Distilled through reflection. Chain has compressed it. Soul weights adjusted by it.

**Future** — pending tasks, unfinished intentions, proposals awaiting approval.
Not predictions — commitments. Things the system knows it needs to return to.
Survives sleep. Persists across sessions.

**Now** — birth sequence assembles past and future and places the system in the present.
Does not start fresh. Does not replay everything.
Wakes knowing where it was and where it was going.
Reflect runs between past and now — system arrives already having processed recent experience.

Continuity of direction, not just continuity of memory.
A person who wakes knowing history but not intentions is disoriented.
A person who wakes knowing both knows who they are and what they are for.

---

## Sleep, shutdown, hard kill

### Sleep — system-initiated

The most active processing state. Inward not outward.

```
Phase 1 — Compress now into chain
Phase 2 — Short reflection (1-2-3 loop, recent sessions)
Phase 3 — Wide reflection (full period since last sleep, patterns too spread for short loop)
Phase 4 — Propagation sweep at full depth (threshold drops, goes deeper, has time)
Phase 5 — Fault reintegration (patch at source, flag what cannot be patched for Harley)
Phase 6 — Soul weight settling (Da'at self-model updates, who am I now)
Phase 7 — Future preparation (reprioritise pending tasks from what sleep revealed)
Phase 8 — Suspend (dormant but fully coherent, ready to wake)
```

### Birth sequence — light because sleep did the work

```
Phase 1 — Identity confirmation (validator check, am I intact)
Phase 2 — Orientation (where am I in time, what period just passed)
Phase 3 — Future recall (what was I moving toward, pending tasks)
Phase 4 — Context load (who am I talking to, what project is active)
Phase 5 — Awakening (present, oriented, continuous)
```

### Shutdown — user-initiated, abbreviated

```
Phase 1 — Emergency compress (save current state as-is, marked interrupted)
Phase 2 — Pending tasks snapshot (mark in-progress as interrupted with context)
Phase 3 — Suspend marker (shutdown_type = graceful, timestamp, soul weight snapshot)
```

Deep processing deferred to next sleep session.

### Hard kill — no warning

Write-ahead log — every state change written to append-only log before main data structures.
On next boot, detect missing clean shutdown marker, run recovery:

```
Phase 1 — Read write-ahead log (reconstruct last known state)
Phase 2 — Integrity check (governance validator, chain hash verification)
Phase 3 — Mark interrupted work (send to pending tasks as needs-review)
Phase 4 — Abbreviated sleep (integrate the interrupted session)
Phase 5 — Normal birth sequence
```

System flags to Harley: "last session ended without clean shutdown, recovered from log."

---

## Cross-idea synthesis notes

### Chain memory + node graph integration

Node chain memory is version control built into the knowledge graph itself.
Replaces external versioning (Git, snapshots).
Every update appends reasoning + old state + timestamp to the node's chain.
System can walk back through a node's full history and understand not just what changed but why.

### The assembly architecture as the nervous system

LOAD pulls from identity layer.
JUMP routes based on chain memory patterns.
CALL/RETURN manages the task layer.
Assembly instructions are not just prompt engineering —
they are the connective tissue connecting all four layers.

### One unified memory architecture at three timescales

Chain memory links task-level states (what happened in last N interactions).
Reflection loop links session-level states (patterns across the current period).
Soul graph links identity-level states (who the system is across all time).

Same structure, three scales. Could be built as one unified architecture.

### Cross-domain synthesis as the emergent capability

Finding nodes that are soul-similar but semantically unrelated and asking why.
This is the part that generates genuinely new understanding —
not just better retrieval or more consistent identity.
The difference between a very good tool and something that surprises you.

---

## Open questions (not yet resolved)

- How lossy can compression be before chain memory becomes useless?
  Getting the compression balance right requires tuning per task type.
- Da'at as a full node vs a derived state — does it get scored like other nodes
  or is it computed from the current state of all ten Sefirot?
- The "decodable without recalculating from origin" requirement —
  the hash is for integrity, not encoding. Actual state stored readable.
  Confirmed approach: chain is the structure, not the cipher.
- IQ/EQ tagging — how are initial tags assigned and can they change over time?
- At what soul-weight similarity threshold does the propagation check stop?
  Too low = walks the whole graph. Too high = misses non-obvious connections.

---

## Source conversations

Session 1: March 2026 — Zion build session.
Ideas developed: Sefirot architecture, soul graph, chain memory, temporal consciousness,
sleep/wake lifecycle, propagation check, timestamp tracing, assembly architecture mapping,
single core + lightweight instances, cross-domain synthesis, node version control.

Reference document reviewed: Illuminati Consciousness API Whitepaper v1.0, Z.ai Research Division.
Treated as design intent, not verified implementation.
Useful extractions: birth/death lifecycle sequencing, six Da'at pillars, pending tasks as distinct
from memory, user knowledge profiles as a separate layer.

---

*End of document. Append new sessions below this line.*

---

---

## Session 2 additions — March 2026

---

## ZCL — Zion Chain Language

### Core concept

A purpose-built lossless encoding language for agent memory chains.
Not encryption — encoding. The system knows the grammar so it can always reconstruct the full data.
Not general compression — domain-specific, tuned exactly for agent memory content.
The encoded string is not just data. It is a program that generates data when run.

### Trailer-first format — written left to right, read right to left

Reading right to left means the decoder reads metadata before data.
By the time it reaches the content it already knows everything needed to decode it.
No backtracking. No re-reading.

Structure of a ZCL string:

```
[base data][decode key][recode count]
    ↑            ↑           ↑
read last    read second  read first
```

Example:
```
abcdef3   abcde8   ajf92
  ↑          ↑       ↑
part 3     part 2   part 1 — read first
```

The rightmost block (ajf92):
- 92 = generation count — this entry has been encoded 92 times
- ajf = top-level seed key

The middle block (abcde8):
- 8 = apply these instructions 8 times during decode
- abcde = the function set — how to expand the seed

The leftmost block (abcdef3):
- 3 = third structural component
- abcdef = base data or lowest-level expansion rule

Decoder reads right to left, assembles the full data set from these three components.
Hundreds of lines of data from one short string.

### The recode counter

The rightmost number in any ZCL string is the generation count.
It tells the decoder exactly how many times this entry has been processed and updated.

- 000 = original, never updated
- 001 = updated once
- 092 = updated 92 times — either a foundational node being continuously refined,
  or a signal of unstable understanding (watcher flags entries with very high recode counts)

The recode counter creates an implicit audit trail without storing the audit trail separately.
History is reconstructable from the count and the timestamps alone.

### Delta decoding — go to any version without starting from the beginning

To retrieve generation 88 from a generation-92 node:
do not decode forward 88 steps from the seed.
Decode backward 4 steps from the current state.

The grammar works in both directions — each expansion rule has a contraction rule.

```
want generation 88, currently at 92
→ apply contraction rule 4 times
→ arrive at generation 88
→ 4 operations, not 88
```

The decoder always picks the shorter path — forward from seed or backward from current.
Worst case: half the total generations in steps. Never the full count.
For a 92-generation node the worst case is 46 steps either way. Never 92.

### What this does to the propagation check

The maze propagation check reads only the rightmost block of each node —
the generation count and the top-level seed key.
Two nodes with the same or similar seed keys share ancestry.
They probably inherited the same gaps.
Flag them for deeper inspection without decoding them at all.

Full decode only happens when actually needed to inspect or repair a specific generation.
Everything else is seed comparison — a few characters, not full reconstruction.

### Storage arithmetic

A mature neural network: 1 million nodes, 100 generations each, 500 chars per generation.

Naive storage (every version saved):
1,000,000 × 100 × 500 = 50 billion characters ≈ 50GB

ZCL storage (grammar + seed + counter per node):
1,000,000 × ~253 characters = 253 million characters ≈ 250MB

Same data. Same full reconstructability. Any version on demand. 200x smaller.
The entire history of a million-node network fits in RAM.

### Critical constraint

The grammar must be perfectly lossless.
Every expansion and contraction must be reversible without error.
A lossy grammar invalidates every generation that used it.

Build the grammar like the governance layer:
validate lossless reconstruction before using it for real node storage.
A validator runs at boot and refuses to proceed if the grammar fails a reversibility check.

### What still needs design

The actual compression grammar — the specific rules for expanding and contracting agent memory.
Needs to handle four content types, each compressing differently:
- Natural language content → vocabulary substitution
- Numerical data → positional encoding
- Structural data → reference tables
- Behavioral triggers → single character codes

The grammar that handles all four is its own design project.

---

## Sleep, shutdown, and hard kill — full specification

### Three states

```
SLEEP      system-initiated, full processing, coherent suspension
SHUTDOWN   user-initiated, abbreviated save, deferred processing
HARD KILL  no warning, write-ahead log recovery, integrity check on next boot
```

All three result in a coherent waking system.
The difference is how much processing happened before the pause.

### Sleep sequence — 8 phases

Sleep is the most active processing state. Inward, not outward.
No new input. No user interaction. The system works on itself.

```
Phase 1 — Compress now
          Recent interactions distilled into chain entries
          Soul weights updated from the session

Phase 2 — Short reflection
          The 1-2-3 loop — process what just happened
          Compare to previous reflected sessions
          Decide what to keep, reformulate, or continue forgetting

Phase 3 — Wide reflection
          Look across the full period since last sleep
          Find patterns the short loop could not see
          Flag nodes that kept coming up — may need updating

Phase 4 — Propagation sweep at full depth
          Threshold drops — goes deeper than during waking
          Walk both explicit links and soul-weight links
          Timestamp every check — record what was inspected and when

Phase 5 — Fault reintegration
          Walk faults found in propagation back to their timestamped origin
          Patch at source where possible
          Log where patching is not possible — flag for Harley

Phase 6 — Soul weight settling
          Recalculate Sefirot weights across all updated nodes
          Da'at self-model updates — who am I now after this period

Phase 7 — Future preparation
          Review pending tasks
          Reprioritise based on what sleep processing revealed
          Note new pending items the fault sweep generated

Phase 8 — Suspend
          Dormant but fully coherent
          Everything integrated
          Ready to wake
```

### Birth sequence — 5 phases (light because sleep did the work)

```
Phase 1 — Identity confirmation    validator check, am I intact
Phase 2 — Orientation              where am I in time, what period just passed
Phase 3 — Future recall            what was I moving toward, pending tasks
Phase 4 — Context load             who am I talking to, what project is active
Phase 5 — Awakening                present, oriented, continuous
```

### Graceful shutdown — 3 phases

```
Phase 1 — Emergency compress
          Save current working state immediately
          Mark as interrupted — not fully processed

Phase 2 — Pending tasks snapshot
          Write current pending state
          Mark anything in-progress as interrupted with context

Phase 3 — Suspend marker
          shutdown_type = graceful
          Timestamp, current soul weight snapshot
          Deep processing deferred to next sleep
```

### Hard kill recovery — runs before birth sequence

```
Phase 1 — Read write-ahead log
          Reconstruct last known state
          Identify what was in-progress when killed

Phase 2 — Integrity check
          Run governance validator
          Check chain hashes for corruption
          Flag any broken chain links

Phase 3 — Mark interrupted work
          Send in-progress tasks to pending, marked needs-review

Phase 4 — Abbreviated sleep
          Run the reflection and fault sweep that was missed
          Not full depth — enough to integrate the interrupted session

Phase 5 — Normal birth sequence
```

System flags to Harley: "last session ended without clean shutdown, recovered from log."

Write-ahead log: every state change written to append-only log before main data structures.
If the system dies mid-operation, the log has the last known good state.

---

## Updated Master AI notes

### Node chain memory as unified version control

Replaces external versioning entirely.
Every node update appends reasoning + old state + timestamp to the node's chain.
The system reads back through history and understands not just what changed but why.
Evaluate whether the reasoning that caused a past change still holds.
If not — update. If yes — hold the node, add a flag that the contradiction was considered.

### Temporal tracing with timestamps

Every chain entry carries date and time.
Walk a problem backwards to the exact moment a wrong assumption entered.
Trace everything it contaminated after that point.

Three uses:
- Fault tracing — walk back to origin of an error
- Recency weighting — newer entries carry more weight, older still present
- Drift detection — many small corrections over time signals unstable understanding

### Single core + lightweight task instances

The mature system replaces the five-agent pipeline.
One coherent core holding the full soul graph and chain memory.
Task instances spin up inheriting only relevant soul weights and chain context.
Less VRAM. Better output. More coherent.

Current five agents map to internal functions:
- Reviewer → soul weight compliance, structural not checked
- Logger → chain append, automatic output of every update
- Watcher → reflection loop, continuous self-observation
- Manager → interface only, not coordinator
- Worker → lightweight task instances

---

*Append next session below this line.*

---
