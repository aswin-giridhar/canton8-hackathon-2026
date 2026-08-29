# Brainstorm — API track and Daml track

Working notes, not a spec. Written 29 Aug 2026 against the measured DevNet
findings in `00-canton8-hackathon-context.md`.

Everything here is filtered through the published rubric, because the rubric is
unusually specific about what earns points:
**measure it (30%) · survive attack (25%) · works outside the demo (20%) ·
honesty (15%) · would ship (10%).**

---

## The strategic observation

**A1 and A2 are the same system viewed from two ends.**

A1 builds an index of the ledger. A2 checks a database against the ledger and
catches drift. If you build A1 *with a reconciler bolted on*, the reconciler is
A2 — and, more importantly, it is the **number** that the 30% criterion is asking
for. "My index matches the ledger, continuously, and here is the drift counter"
is simultaneously the A1 correctness proof and the A2 deliverable.

Most teams will build A1 and demo a balance endpoint. A balance endpoint is not a
measurement. A drift counter that has been running for an hour is.

One fork is already named `Scandex` and one `canton-agent-mandate`, so A1 and D1
both have at least one team on them. Nobody has pushed code yet.

---

## A1 — the scanner

### What the challenge actually says
Read the ACS for balances, stream forward to stay current, persist it, serve
balance + transfer history, and resume after a restart without re-reading
everything. Judged: correctness first, then clean resume, then history depth.

### The three traps the toolkit warns about
1. **ACS first, then stream.** Streaming from the current end gives you the
   future, not the present — balances read zero.
2. **`InterfaceFilter`, not `TemplateFilter`.** `Holding` is an interface; a
   template filter returns `200 OK` + empty list, which is indistinguishable from
   a zero balance.
3. **Transactions are trees.** You have to walk them, not iterate a flat list.

### The trap the toolkit does NOT warn about — and it is the one that bites
**The DevNet token lives 900 seconds and `c8lab.py` never refreshes it.**

A1's core requirement is a continuously streaming service. That service will 401
at minute 15. It will look like a streaming bug, a WebSocket bug, or a network
bug, and it is none of those. Handling this on line one is a free lead over every
other team on this track.

### Additional hazards measured this session
- `/v2/parties` is paginated (10,000 cap, `nextPageToken`). Party discovery that
  reads one page silently sees a partial network.
- 5,784 local parties on DevNet. Any per-party loop is a scale problem, not a
  demo detail. This is the "works outside the demo" criterion handed to you.
- `activeAtOffset` on the ACS query **must** equal the offset you then stream
  from. Off by one and you either double-count or lose events.

### Sketch
```
bootstrap:  ACS at offset O (InterfaceFilter on Holding)  ->  SQLite
stream:     WS /v2/updates from O forward
apply:      walk tree; created -> insert holding, archived -> delete
checkpoint: write offset in the SAME sqlite transaction as the events
serve:      GET /balance/{party}, GET /transfers/{party}, GET /metrics
reconcile:  periodically re-query ACS, diff against index, export drift
```

The atomicity detail is where correctness actually lives: if the offset is
committed separately from the events, a kill between the two either loses events
or replays them. One transaction, or an idempotent apply keyed on event id.

### The demo that scores
`kill -9` mid-stream, restart, show it resumes at the stored offset and the
reconciler still reports zero drift. Then show the drift counter's history.

### Numbers to bring
Parties indexed · holdings tracked · reconciliation drift over N minutes ·
resume time after kill · stream lag vs ledger end · events/sec.

---

## A2 — the drift catcher

### What it is
Hold one invariant — *every row marked `submitted` has a matching active contract
within 60s* — check it continuously, act on violations, expose metrics. They will
inject drift in front of you and time you, then ask what happens at a million rows.

### The million-row answer is the whole interview
You cannot full-scan. The answer they are fishing for:

**Only the open set is scannable.** Rows in a non-terminal state, indexed by age,
walked with a cursor and a high-water mark. Terminal rows leave the working set
permanently and are never scanned again. Bounded work per tick, resumable
mid-sweep. Have this answer ready as a sentence, not as a diagram.

### The dangerous part nobody mentions
A reconciler that *acts* can make things worse. If "no matching contract" triggers
a retry, and the real cause was that your read was stale, you have just
double-spent.

Two defences worth building and saying out loud:
- **Deterministic `commandId`.** Canton deduplicates on it. A retry with the same
  commandId is safe; a retry with a fresh uuid is a second payment. `c8lab.py`
  generates `f"c8lab-{uuid.uuid4()}"` — fine for a lab, wrong for a retry loop.
- **Separate the diagnosis channel from the action channel.** A checker that
  returns "drift" into the same path that executes fixes will eventually execute
  a wrong fix. Report, then act on an explicit policy, with every action logged.

### Numbers to bring
Time-to-detect for injected drift · drift age distribution · actions taken by
type · false-positive rate · scan cost per tick at N rows.

---

## D1 — the agent mandate wallet

### Where the starter leaves you
`Mandate.daml` already has: cap, `spent`, expiry field, `Charge` (spender-only),
`Revoke` (owner-only, unblockable), `Adjust` (both signatures), and a
propose/accept pair. `Test.daml` proves cap-exceeded and post-revoke both fail.

It **does not** move any money, has **no allow-list**, and has **no audit trail**.
Those three are the task.

### What the judges said they will do
> "We will try to make your agent exceed its cap, and pay someone it should not.
> Both must fail **on the ledger**, not in your API. Be ready to show us the line
> of Daml that stops it. Then we will revoke and try again."

So the deliverable is not a wallet. It is **a wallet plus a rejection suite**, and
the rejection suite is the thing being graded.

### The hard part, named early
Making `Charge` actually move value. The obstacle people hit: a Daml choice body
cannot call the registry over HTTP, and the token transfer needs the registry's
choice context and disclosed contracts.

The resolution — and this is the design hypothesis to de-risk first:

- A choice body executes with **the contract's signatories' authority** plus the
  choice's controllers. The starter's own README states this: *"Inside a choice
  body you have the contract's signatories plus that choice's controllers."*
- `Mandate` has `signatory owner, spender`. So a `Charge` controlled by the
  spender runs **with the owner's authority** and can therefore move the owner's
  holdings — no hot key, no owner signature at call time.
- The registry context is fetched off-ledger and passed **in** as a choice
  argument, with the disclosed contracts attached at submission.

That is the whole architectural claim of the project, and it is exactly the thing
worth verifying in the first hour rather than the last. **Unverified so far** —
`daml` is not installed on this machine yet.

### Attack surface to close before they try it
| Attack | Defence |
|---|---|
| charge over the cap | `assertMsg (spent + amount <= cap)` |
| pay a party not on the list | `assertMsg (elem receiver allowed)` |
| charge after revoke | `Revoke` is consuming — the contract is gone |
| charge after expiry | `assertMsg (now < expiresAt)` — **not automatic** |
| negative amount to inflate headroom | `assertMsg (amount > 0.0)` |
| agent raises its own cap | `Adjust` controlled by `owner, spender` both |
| replay the same charge | consuming choice archives the mandate cid |

The expiry one is worth calling out: `expiresAt` is just a field. Nothing checks
it unless you write the check. The starter notes this was a real audit finding on
production Canton code.

### Sequencing (de-risk order)
1. Cap + allow-list + expiry + revoke, pure Daml, with the full rejection suite.
   Cheap, fast, and it is the majority of the score.
2. Audit trail: every `Charge` emits a `ChargeRecord` contract naming the amount,
   the counterparty, the time, **and which rule permitted it**. That is the
   "readable by a human" requirement, answered literally.
3. Only then wire real value movement through the token standard.

Doing (3) first is the trap — it is the only part that can fail for reasons
outside your control.

### Numbers to bring
Attack cases attempted vs rejected on-ledger · the specific Daml line for each ·
charges executed end-to-end · latency per charge · `daml test` runtime.

---

## Cross-cutting: things true of any track

- **Credential clock.** The token is 15 minutes. Anything long-running needs
  refresh. This is the single most reusable finding of the day.
- **Two registries, two admins.** Amulet lives on `sv-proxy` with the DSO as
  admin; `c8ETH`/`c8BTC`/`c8TEST`/`rCC` live on `token-registry` under `/api/c8`
  with `cantor8-digik-1::…` as admin. `C8_ADMIN_PARTY` must match the token.
- **Amulet already serves Token Standard V2 on DevNet** (`transfer-instruction-v2`,
  `holding-v2`, `allocation-v2`, `transfer-events-v2`) alongside v1. That is a
  live reference implementation to read, and it matters for anyone circling the
  V2 accelerator problem.
- **Registries document themselves.** POST `{"choiceArguments":{}}` to a factory
  endpoint and the 400 names the exact missing field.
- **Say what is mocked.** 15% of the score, and the cheapest points available.
