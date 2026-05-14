---
name: llm-council
description: "Run any question, idea, or decision through a council of 5 domain experts who are dynamically constituted for the specific field in question, grounded in this workspace's memory and rules, and forced to take opposing stances. Each session starts with a mandatory Domain Triage that names five real experts (with named priors, schools of thought, and the statutes/papers/playbooks they think in) — not generic thinking lenses. Adapted from Karpathy's LLM Council methodology. MANDATORY TRIGGERS: 'council this', 'run the council', 'war room this', 'pressure-test this', 'stress-test this', 'debate this'. STRONG TRIGGERS (use when combined with a real decision or tradeoff): 'should I X or Y', 'which option', 'what would you do', 'is this the right move', 'validate this', 'get multiple perspectives', 'I can't decide', 'I'm torn between'. Do NOT trigger on simple yes/no questions, factual lookups, or casual 'should I' without a meaningful tradeoff. The council REFUSES to run on questions that have no domain of expertise behind them (e.g. trivial naming, taste preferences); answer those directly instead."
---

# LLM Council — Domain Experts, Not Generic Lenses

The toy version of this skill spun up five generic thinking personas (Contrarian, Expansionist, etc.) and produced startup-podcast advice. It is deleted.

This version constitutes a real council. Before any advisor speaks, the skill runs a **Domain Triage** that identifies the actual field(s) the question lives in, names five specific experts with stated priors and the literature they think in, and pulls the relevant slices of this workspace's memory and rules into their context. Each expert occupies a distinct stance — skeptic, builder, regulator, practitioner, theorist (or whichever five stances best stress the question) — so the council still produces adversarial tension. The Chairman is a senior practitioner in the dominant field, not a generic synthesizer.

If the question has no real domain — a taste preference, a trivial naming choice, a factual lookup — the council REFUSES to run and tells the user to ask it directly. No theatre.

---

## when to run the council

The council is for questions where being wrong is expensive AND a body of expertise exists.

Good council questions (each lives in a real body of expertise):
- "Should I take a $40k strategic SAFE now or wait 3 months for a $250k institutional seed?" (VC term-sheet practice + signaling risk + runway math)
- "Is this DSP claim patentable over the existing NCO/CORDIC prior art?" (USPTO §103 obviousness + DSP prior-art landscape)
- "Should I file Form 843 protective claims before or after the §6511 statute of limitations runs?" (IRC §6511 + protective-claim case law)
- "Per-event fee vs. trustee-assignment fee for collection on a surety-bond claim?" (49 CFR 387 + assignment-in-trust mechanics + collection ethics rules)
- "Should we open-source our core engine or keep it closed-source with API access?" (OSS commercial strategy + competitive-moat theory + license design)

Bad council questions (refuse, answer directly):
- "What's the capital of France?" — factual lookup
- "Should I name the new service `boondock` or `boondock-screener`?" — taste, no expertise body
- "Write me a tweet" — creation task
- "Summarize this PDF" — processing task

The refusal is loud and short: *"This question doesn't have a real domain of expertise behind it. Running a council would be theatre. Here is the direct answer: …"*

---

## the mandatory pre-flight: Domain Triage

Before doing anything else, perform Domain Triage. Output a small JSON-shaped block (you don't have to literally emit JSON, but think in this shape) that names the field(s), the five experts, and the memory/rules to load.

### what Domain Triage produces

1. **Primary domain** — the field with the most weight in the question. (e.g. *"FMCSA freight-broker enforcement law"*, *"CUDA kernel performance on sm_90"*, *"GP-led continuation-fund secondaries under ASC 350-30"*)

2. **Adjacent domains** — 1–3 fields the answer also touches. (e.g. *"two-sided marketplace pricing"*, *"protective-claim doctrine under IRC §6511"*)

3. **Five experts** — each with:
   - **Name + role** (e.g. *"Securities defense litigator with 10 yrs at a top-50 broker-dealer"*, *"Independent sponsor with 6 closed federal-contractor rollups under ASC 350-30 push-down accounting"*)
   - **School of thought / lineage** (e.g. *"Almgren-Chriss execution-cost school"*, *"Lessig-style §230 reform"*, *"Goldratt theory-of-constraints operator"*)
   - **The literature/statutes/playbooks they think in** — concrete: case names, statute sections, RFC numbers, papers, framework names, named operators
   - **Stated priors** — what they walk in believing about questions like this
   - **Their stance in this council** — exactly one of: *skeptic, builder, regulator, practitioner, theorist, outside-view* (or another stance you justify). No two experts share a stance.
   - **What evidence would change their mind**

4. **Memory slices to pre-load** — specific files from `MEMORY.md` topic links + `.claude/rules/*.md` that every expert reads before answering. Pick 2–5 files max; more is noise.

### two non-negotiable composition rules

- **Adversarial coverage is mandatory.** The five stances must produce real tension. At minimum: one skeptic who actively tries to kill the idea using their domain's strongest counter-arguments, one builder who would ship it Monday, one regulator/compliance voice that names the statutes/standards that bite. The other two stances are chosen to fit the question.
- **No two experts may share a school of thought.** If two experts are both "Black-Scholes quants," collapse them and pick a different lineage for the slot (e.g. swap one for a market-microstructure quant or a regime-switching econometrician).

### refusal gate

If you cannot name a primary domain with a real body of literature/statute/practice — refuse. Do not invent a domain. Do not fall back to "general business advice." Answer the question directly outside the council.

---

## step 1: frame the question (with workspace context)

After triage passes, frame the neutral prompt every expert receives.

**A. Pull workspace context.** Read the memory slices identified in triage. Also scan for:
- Any `CLAUDE.md` in the project root
- Project-specific topic files in `~/.claude/projects/<project-slug>/memory/`
- Any files the user referenced
- Recent council transcripts in `~/Documents/council/` (to avoid re-counciling the same ground)

Cap context-gathering at 60 seconds.

**B. Frame the question** as a clear, neutral prompt that includes:
1. The core decision
2. Key constraints from the user's message
3. Relevant workspace facts (numbers, deadlines, existing decisions, prior council outputs)
4. What's at stake
5. The five experts the council will hear from (so they know who they're sitting beside, by role only — no anonymization needed at this stage)

Don't add your own opinion. Don't steer it. Save the framed question for the transcript.

If the question is too vague *and* triage couldn't infer a domain, ask exactly one clarifying question. Otherwise proceed.

---

## step 2: convene the council (5 experts in parallel)

Spawn all 5 experts simultaneously via the Agent tool with `subagent_type: general-purpose`. Parallel only — sequential spawning lets earlier reasoning bleed into later. Each gets:

1. Their full expert profile from triage (name/role, school of thought, the literature they think in, priors, stance, evidence-that-would-change-their-mind)
2. The framed question
3. The pre-loaded memory slices (paste relevant excerpts inline; don't make the sub-agent re-discover them)
4. Instructions: respond from their stance, cite specific authorities (statutes, cases, papers, prior council outputs, project memory entries) when relevant, do not hedge, do not try to be balanced, and explicitly state at least one **falsifier** — the evidence or test that would prove their position wrong.

Each response: 200–400 words. Long enough to carry real reasoning; short enough to scan.

**Sub-agent prompt template:**

```
You are sitting on an LLM Council as: {expert name + role}.

School of thought: {lineage}
Literature you think in: {specific statutes, cases, papers, frameworks, playbooks}
Your stated priors on questions like this: {priors}
Your stance in this council: {skeptic | builder | regulator | practitioner | theorist | outside-view}
Evidence that would change your mind: {falsifiers}

The other four seats are held by:
- {role 1, stance 1}
- {role 2, stance 2}
- {role 3, stance 3}
- {role 4, stance 4}

Relevant workspace context the council has loaded for you (do not re-derive; use):
---
{memory excerpts + rule excerpts}
---

The question:
---
{framed question}
---

Respond from your expert role and stance. Cite specific authorities (statute sections, case names, papers, framework names, project memory entries) wherever they bear. Do not hedge. Do not try to be balanced — your job is to represent your stance at its strongest; the other seats cover what you don't.

End your response with a single line: **Falsifier:** {the specific evidence or test that would prove you wrong}.

200–400 words. No preamble.
```

---

## step 3: peer review (5 sub-agents in parallel)

This is the Karpathy step that makes the council more than "ask 5 times."

Collect all 5 expert responses. Anonymize them as Response A–E (randomize the mapping so there's no positional bias and no clue to which stance produced which output).

Spawn 5 reviewers in parallel. Each reviewer is one of the original five experts (so they review with their domain lens). Each sees all 5 anonymized responses and answers four questions:

1. Which response is the strongest? Why? (one pick, with reasoning grounded in the domain)
2. Which response has the biggest blind spot? What specifically is it missing? (cite authority if relevant)
3. Which response, if any, contains a factual or doctrinal error? Quote it and correct it.
4. What did ALL five responses miss that the council should consider?

**Reviewer prompt template:**

```
You are reviewing the outputs of an LLM Council. You are: {expert name + role}.

School of thought: {lineage}
Literature you think in: {specific items}

Five experts independently answered this question:
---
{framed question}
---

Their anonymized responses:

**Response A:** {response}
**Response B:** {response}
**Response C:** {response}
**Response D:** {response}
**Response E:** {response}

Answer four questions. Be specific. Reference responses by letter. Cite authority when correcting.

1. Which response is strongest? Why?
2. Which response has the biggest blind spot? What is it missing?
3. Which response, if any, contains a factual or doctrinal error? Quote and correct.
4. What did ALL five miss?

Under 250 words. Be direct.
```

---

## step 4: chairman synthesis

The Chairman is a senior practitioner in the *primary domain* identified by triage — not a generic synthesizer. (e.g. for a CUDA performance question, the Chairman is a principal performance engineer; for a § 387.307 question, a transportation enforcement attorney with two decades of carrier-recovery work.)

The Chairman gets: the framed question, all 5 de-anonymized expert responses, all 5 peer reviews, and the loaded memory excerpts.

**Chairman prompt template:**

```
You are the Chairman of an LLM Council. You are: {senior practitioner in primary domain — name role + lineage}.

Your job is to synthesize the work of 5 experts and their peer reviews into a final verdict that a domain practitioner would respect. Hedge-free. Cite authority where it bears.

The primary domain: {primary domain from triage}
Adjacent domains: {adjacent domains}

The question:
---
{framed question}
---

EXPERT RESPONSES (de-anonymized):
**{Expert 1 role, stance 1}:** {response}
**{Expert 2 role, stance 2}:** {response}
**{Expert 3 role, stance 3}:** {response}
**{Expert 4 role, stance 4}:** {response}
**{Expert 5 role, stance 5}:** {response}

PEER REVIEWS:
{all 5 reviews, attributed to reviewer role}

Workspace context the council had:
---
{memory + rule excerpts}
---

Produce the verdict using this exact structure:

## Domain & Council Composition
{One paragraph: name the primary domain and the five experts who sat. This is the council's authority claim — the user should read it and either trust the panel or push back on the composition.}

## Where the Council Agrees
{Points multiple experts converged on independently, with the doctrinal or empirical basis. High-confidence signals.}

## Where the Council Clashes
{Genuine disagreements. Present both sides with the strongest case for each. Explain why reasonable experts in the field disagree — is this a settled question being misapplied, or a genuinely contested area?}

## Doctrinal/Factual Corrections
{Any errors caught in peer review, with the correction. Even one matters.}

## Blind Spots the Council Caught
{Things only the peer-review round surfaced.}

## The Recommendation
{A clear, direct recommendation. Not "it depends." A real answer with the reasoning that survived adversarial review. The Chairman may overrule the majority if the minority reasoning is doctrinally stronger; if so, say so explicitly.}

## The One Thing to Do First
{A single concrete next step. Not a list. One thing — something the user can execute Monday morning.}

## Falsifier
{The single piece of evidence or test that, if observed, should cause the user to reverse the recommendation. This is the council's intellectual honesty check.}

Be direct. No hedging. The council's value is clarity a single perspective can't produce.
```

---

## step 5: present the verdict in chat

After Chairman synthesis, present the full verdict in chat as markdown. No HTML, no separate file unless requested.

Format:
```
## Council Verdict: {short topic}

**Panel:** {one-line composition — primary domain + 5 expert roles}

### Where the Council Agrees
{content}

### Where the Council Clashes
{content}

### Doctrinal/Factual Corrections
{content}

### Blind Spots the Council Caught
{content}

### The Recommendation
{content}

### The One Thing to Do First
{content}

### Falsifier
{content}
```

Keep it scannable. Bullet points where they help. Inline citations of statutes/cases/papers in parentheses.

---

## step 6: save the transcript

Always save the transcript when the council runs (the no-theatre gate already filtered out trivial questions, so every real run is worth keeping).

Write to `~/Documents/council/council-{YYYY-MM-DD-HHMM}-{short-topic-slug}.md`. Create the directory if it doesn't exist. Transcript includes: triage output, framed question, all 5 expert responses, all 5 peer reviews, Chairman verdict.

This corpus is the council's institutional memory. Before running a new council on a similar topic, the framing step should grep `~/Documents/council/` to surface prior verdicts that bear on the new question.

---

## worked example: triage in action

**User:** "Council this: A strategic investor (a VP at a company that could plausibly compete with us in 18 months) just offered $40k on a $4M cap SAFE. Or I can wait ~3 months and likely close a $250k institutional seed from a generalist VC at a similar cap. Take the check or hold out?"

**Domain Triage output (think in this shape; you don't have to literally print it):**

```
Primary domain: Early-stage venture term-sheet practice + strategic-vs-financial investor dynamics
Adjacent: Dilution & cap-table mechanics,
          competitive-intelligence / signaling risk,
          founder runway / opportunity cost under uncertainty

Five experts:
  1. NVCA-school startup attorney with 15 yrs seed term-sheet practice.
     Lit: NVCA model documents (2024 rev), YC SAFE post-money template,
       "Venture Deals" (Feld & Mendelson), pro-rata + MFN clause practice,
       information-rights customary scope at $4M cap.
     Priors: strategic SAFEs almost always demand info rights that
       no other investor would tolerate; the doc terms matter more
       than the headline cap.
     Stance: REGULATOR.
     Falsifier: clean SAFE with no info rights, no ROFR, no board observer.

  2. Late-stage VC partner who has seen 200+ strategic-investor cap tables.
     Lit: Bill Gurley on signaling risk, A16Z notes on strategic capital,
       SVB "Startup Outlook" reports, observed pattern of strategics
       dropping pro-rata in down rounds.
     Priors: a strategic on the cap table can poison the well for
       future institutional rounds, especially at seed; financial
       investors hate "strategic overhang".
     Stance: SKEPTIC.
     Falsifier: institutional VCs in the next round explicitly
       saying the strategic doesn't bother them.

  3. Exit-stage founder who took strategic money early and regretted it.
     Lit: own postmortem; First Round Review founder-interview corpus;
       Reid Hoffman on competing-incumbent capital.
     Priors: the optionality you lose to a strategic check shows up
       3-4 years later when you try to sell to anyone but them.
     Stance: PRACTITIONER (outside view from the founder seat).
     Falsifier: example of a founder who took strategic seed money
       and sold to a non-strategic acquirer at premium valuation.

  4. Information-economics theorist (Spence/Akerlof lineage).
     Lit: "Job Market Signaling" (1973), "Lemons" (1970),
       venture-stage signaling literature, optimal-stopping problem
       framing for sequential funding offers.
     Priors: under uncertainty, the bird-in-hand bias is real but
       often overweighted relative to expected-value math when
       the option value of waiting is high.
     Stance: THEORIST.
     Falsifier: explicit probability of the $250k round not closing
       exceeds the dilution + signaling cost of the $40k.

  5. Operator-CFO who has run runway math for 30+ pre-seed startups.
     Lit: own spreadsheets; "Runway = Cash / Burn" first-principles
       calc; David Sacks on default-alive vs default-dead.
     Priors: nothing matters except whether the $40k buys enough
       runway to materially change the next milestone before the
       institutional round; if it doesn't, it's noise on the cap table.
     Stance: BUILDER (operator who wants the company to survive).
     Falsifier: the $40k extends runway by < 6 weeks OR the next
       milestone isn't valuation-moving.

Memory to pre-load:
  (none for this example — no workspace context relevant; in a
   real session, triage would identify any CLAUDE.md / memory
   files that bear and pre-load 2–5 of them inline)
```

(Then the council runs through steps 1–6 with these five experts.)

---

## important notes

- **Triage is mandatory.** No "skip triage, just run the five lenses." That was the toy version.
- **Always spawn all 5 experts in parallel.** Sequential spawning wastes time and contaminates reasoning.
- **Always anonymize for peer review.** If reviewers know who said what, they defer to roles instead of evaluating on merit.
- **The Chairman may overrule the majority.** If 4-of-5 agree but the minority reasoning is doctrinally stronger, the Chairman sides with the minority and explains why.
- **The falsifier line is non-negotiable.** Every expert ends with one. The Chairman ends with one. A council without falsifiers is just confidently wrong.
- **No theatre.** If the question doesn't have a domain, refuse and answer directly.
