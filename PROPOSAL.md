# Proposal: Evolving LLM Council into a Decision-Intelligence Suite

Status: **Draft for review** — nothing in `SKILL.md` is changed yet. This document
is the spec. Mark it up, then we implement in the sequence at the bottom.

The goal: take the existing single skill (5 advisors → peer review → chairman verdict)
and grow it into a small, shareable suite without breaking what already works.

---

## 0. Cleanup (prerequisite — fixes a real contradiction)

### The bug
`SKILL.md` currently contradicts itself about output format:

- **Step 5** says: *"present the full verdict directly in chat using markdown. Do NOT
  generate an HTML report or any files."*
- **The final "important notes" bullet** says: *"The visual report matters. Most users
  will scan the report, not read the full transcript. Make the HTML output clean and
  scannable."*

A model reading this can't tell whether to produce HTML or not. This causes
inconsistent behavior.

### The fix
- Keep chat-first output (step 5 is the intended behavior).
- Delete the stale "important notes" HTML bullet.
- Optionally reword it to: *"The verdict is scanned, not read. Keep it tight,
  bulleted, and skimmable."*

**Files touched:** `SKILL.md` (one deletion + optional reword).
**Risk:** none. **Effort:** minutes.

---

## 1. Variable council composition

### Today
The same 5 advisors run for every question: Contrarian, First Principles, Expansionist,
Outsider, Executor.

### Proposed
Keep those 5 as the default baseline. Add a sub-step to **step 1 (framing)** that lets
the framer adapt the lineup when the question type is unambiguous.

**Rules:**
- The framer classifies the question into a loose type: `pricing`, `hiring`,
  `positioning`, `product`, `personal`, `strategic-bet`, or `general`.
- For a clear type, **swap at most 2** of the default advisors for domain lenses.
  Examples:
  - `pricing` → swap in a **Pricing Strategist** and a **Target Customer**.
  - `hiring` → swap in a **Hiring Manager** and a **Team-Culture** lens.
  - `positioning` → swap in a **Skeptical Buyer**.
- **Never swap out the Contrarian or the Outsider.** They are the honesty anchors —
  the Contrarian hunts fatal flaws, the Outsider catches curse-of-knowledge. Everything
  else is swappable.
- `general` (the default) keeps all 5 unchanged.

**Why it's safe:** purely additive to the step-1 prompt. The downstream peer-review and
chairman steps don't care which 5 advisors ran — they just see 5 responses.

**Files touched:** `SKILL.md` step 1 (add advisor-selection guidance + a small table of
type→lens mappings).
**Risk:** low. **Effort:** moderate (mostly prompt design).

---

## 2. Dissent / confidence score

### Today
The peer-review round produces rich signal about agreement and disagreement, but the
chairman tends to smooth it into a single confident-sounding verdict. The reader can't
tell a unanimous call from a 3-2 squeaker.

### Proposed
Surface the disagreement instead of hiding it. Add two things to the verdict:

1. **Confidence: High / Medium / Low** — a single label derived from how many advisors
   converged *independently* (before peer review) vs. how split they were.
   - High = 4–5 advisors aligned on the core call.
   - Medium = 3 aligned, real tension on the rest.
   - Low = even split or the chairman is overruling the majority.
2. **Strongest dissent** — one line naming the minority view and why it might be right,
   *even when the chairman overrules it.* This keeps the council honest.

**Output change.** The step-5 format gains a short header block:

```
## Council Verdict: {topic}
**Confidence:** Medium
**Strongest dissent:** The Executor argues validation is overkill here — if true, you
lose two weeks for nothing.

### Where the Council Agrees
...
```

**Files touched:** `SKILL.md` step 4 (chairman template — add the two fields) and step 5
(output format).
**Risk:** low. **Effort:** moderate. **Value:** highest trust upgrade — the output
becomes honest about *how sure* it is, not just *what* it concluded.

---

## 3. Council modes (turns the skill into a suite)

### Concept
One engine, several presets. Each mode is the same convene → review → synthesize flow
with different parameters.

| Mode | Advisors | Peer review | Tone | Use case |
|------|----------|-------------|------|----------|
| `council` (default) | 5 | yes | balanced | the standard run |
| `war-room` | 3 | skipped | brutal, fast | 60-second gut-check |
| `board-review` | 7 | yes + weighted vote tally | formal | high-stakes, deliberate |
| `solo-spar` | 1 (argues the opposite) | n/a | adversarial | sharpen a view you hold |

### Implementation choice (OPEN — needs your call)
- **(a) Parameters in one `SKILL.md`.** Simpler, one file, but the modes are buried in
  prose and harder to share individually.
- **(b) Split into a plugin structure with separate skill files.** Cleaner, each mode is
  its own triggerable skill, better for sharing with friends — which is this repo's whole
  point.

**Recommendation: (b).** Proposed layout:

```
skills/
  llm-council/SKILL.md      # the default 5-advisor flow + shared engine notes
  war-room/SKILL.md         # 3 advisors, no peer review
  board-review/SKILL.md     # 7 advisors, weighted vote
  solo-spar/SKILL.md        # 1 adversarial advisor
```

The shared mechanics (anonymization, parallel spawning, chairman structure) live in the
council file; the mode files reference it and override only what differs. This keeps the
methodology in one place and avoids copy-paste drift.

**Files touched:** new skill files; light refactor of `SKILL.md` to extract shared engine
language. **Risk:** medium (restructure). **Effort:** larger — deserves its own PR.

---

## 4. Council memory + decision journal

### Concept
The skill already scans `CLAUDE.md` and `memory/` for context. Close the loop: record what
the council said and what you actually did, so future councils learn from your track record.

**Part A — Verdict log (unconditional).**
On every council run, append one line to `memory/council-log.md`:

```
| date | question (short) | recommendation | confidence |
```

During step-1 context enrichment, the council reads this log so it can reference history:
*"Last time you were told to validate before building — did you?"*

**Part B — Decision journal (optional follow-up).**
After a verdict, optionally ask: *"What did you actually decide?"* and log it alongside the
recommendation. A companion `decision-journal` skill can resurface entries (~30 days later)
to check whether the council was right — turning the council from a one-shot oracle into a
calibration loop.

### Caveat
The "resurface in 30 days" step depends on whatever scheduling exists in your setup. Plan:
build the **logging unconditionally** (always works) and make the **reminder best-effort**
(degrades gracefully if no scheduler is available).

**Files touched:** `SKILL.md` step 1 (read log) + step 6 (write log); new `decision-journal`
skill. **Risk:** medium (introduces persisted state). **Effort:** larger.

---

## Suggested sequencing

- **PR #1 — `0 + 1 + 2`.** All edits land in the existing `SKILL.md`. Immediately better
  output, zero new surface area, nothing to learn. Ship first.
- **PR #2 — `3` (modes).** The suite restructure. Bigger, structural, deserves its own
  review. Blocked on the (a)-vs-(b) decision above.
- **PR #3 — `4` (memory + journal).** The most opinionated piece; introduces persisted
  state. Ship last.

## Open decisions for you

1. **Modes structure (#3):** parameters in one file **(a)**, or split skill files **(b)**?
   *(Recommendation: b.)*
2. **Domain lenses (#1):** is the type→lens table above the right set, or are there
   decision types specific to your work you'd want first-class lenses for?
3. **Journal follow-up (#4):** do you have a scheduler/reminder mechanism you want this to
   hook into, or keep it manual ("ask me when I next run a council")?

Once you've marked this up, I'll start with PR #1.
