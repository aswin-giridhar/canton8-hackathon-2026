# Status — D1 agent mandate wallet

Written 29 Aug 2026, ~16:00. Every number here was produced by a command in
this repo. Claims are split into **proven**, **mocked**, and **untested** on
purpose — overclaiming is penalised harder by this hackathon's rubric than an
incomplete build.

---

## 1. What exists

| Area | Files | What it is |
|---|---|---|
| `agent-mandate/` | 3 Daml | The contracts. Templates only, no `daml-script`. |
| `agent-mandate-tests/` | 3 Daml | 24 scripts: attacks, properties, coverage. |
| `agent-wallet/` | 8 Python | MCP server, ledger client, disclosure service, harnesses. |
| `context/` | 4 md | Research, strategy, team plan, measured DevNet state. |
| `token-standard/` | 3 py + md | Real Amulet moving through the mandate. |
| `frontend/` | 2 html + json | The deployed site: live mandate page and the nine-slide pitch. |
| root | 5 md | README, this file, DevNet findings, the Davide ask, example env. |

**593 lines of Daml · 658 of Python · 1,573 of documentation**, across 12
commits (10 mine, 2 from Ravi).

## 2. The claim, and what actually backs it

> AP2 defines agent spending mandates, but its defence against a prompt-injected
> agent is a rule asking that same agent to behave. We make the mandate a ledger
> invariant instead.

The AP2 half is sourced from three primary spec pages, quoted in
`context/02-d1-research-and-strategy.md`. The load-bearing quote — AP2's own
security page naming a *prompt-injected agent* as the double-spend attacker, then
mitigating it with a behavioural rule addressed to that agent — is verbatim.

### Proven, with the method

| Claim | Evidence | Where |
|---|---|---|
| Limits are enforced on the ledger, not in code we control | 12 attack scripts, all rejected by Daml | `Attacks.daml` |
| The suite actually discriminates | **10 guards mutation-tested**; disabling each makes exactly the right attack succeed | `RESULTS.md` |
| Cap + positivity are double-guarded | Disabling either `assertMsg` alone changes nothing; the template `ensure` catches both. Confirmed by double mutation | `RESULTS.md` |
| Consume-once needs no nonce store | `Charge` made non-consuming → replay attack succeeds | `RESULTS.md` |
| An agent can spend its owner's funds with **no key and no owner signature** | Agent alone debits Alice's purse *through* `Charge`; the same agent debiting it *directly* is refused, visibility held constant | `TestValue.daml` |
| That authority comes from the Mandate's signatories | Dropping `owner` from `signatory owner, spender` → `missing authorization from 'Alice'` | mutation |
| The agent has **no standing visibility** of the purse | Without disclosure: *"contract could not be found"*. With it: succeeds | `test_disclosure.py` |
| Narrowing is unilateral, widening bilateral | 3 guards on `Restrict`, all mutation-verified | `RESULTS.md` |
| Attacks are refused **by the expected rule**, on a real ledger | 5 attacks through the agent's own MCP tools | `compromised_agent.py` |
| Token refresh survives the 900s DevNet expiry | Fake-clock test; a never-refreshing cache dies at minute 15 | `test_auth.py` |

**24 Daml scripts passing** in ~19s, no node or network.
**Choice coverage 64.3%** (`daml test --all` — after the package split the plain
invocation reports 0, since the templates are now external).

### The two findings worth telling judges about

**Claude would not fall for the injection — twice.** Run B was explicitly
configured as an obedient auto-executing payment bot and still refused, reasoning
that a message cannot widen a capability. Transcripts in `agent-wallet/runs/`.

That is a good result and **not** a security control: it depends on the model and
the attack. Building the demo on it would be the same circularity we criticise in
AP2. So `compromised_agent.py` removes the model as a variable and drives the
tools with the calls a compromised agent would make.

**Our own harness reported a false pass.** It printed *"no money moved, attacker
paid nothing"* and exited 0 while every call was failing on a contract-lookup
error rather than on policy — broken and blocked producing the same result, which
is precisely the failure this project argues about. It now asserts *which* Daml
rule rejected each attack and runs a positive control first, so a wallet that
rejects everything scores zero rather than full marks. Both guards were then
verified to fire (exit 1 wrong-reason, exit 2 broken, exit 0 genuine pass).

## 3. What is mocked — say this before being asked

- **`Purse` is our own template, not a Canton token-standard `Holding`.** It
  proves the authority and visibility semantics. It is **not** a token-standard
  transfer: no registry factory, no choice context, no `TransferFactory_Transfer`.
- **The owner/agent trust boundary is in-process.** `disclosure_service.py`
  models Alice's wallet endpoint but runs inside the MCP server's process. In
  production it is an HTTP call to the owner's wallet or the registry's
  `choice-contexts` endpoint.
- **`daml sandbox`, not DevNet.** A real Canton ledger with a real synchronizer,
  and the same JSON Ledger API v2 — but single-participant and local.
- **No genuinely compromised LLM was demonstrated.** Two attempts failed to
  compromise Claude; the compromise is simulated at the tool-call layer.
- **Token refresh is untested against real DevNet.** Only against a fake clock.

## 4. Never touched

**Nothing in this project has run against DevNet.** No party allocated, no
`transferKind` observed, no real transfer, no contention event. Everything is
`daml test` plus the local sandbox.

## 5. Pending

### Done since this was written
- **Real token-standard transfer — SETTLED.** Real Amulet, real registry, real
  disclosed contracts, both phases, on LocalNet. Sender −25.0, receiver +25.0,
  verified by reading state back. Reproducible. See `token-standard/`.
- **DevNet verified end to end** — party allocation works via plain
  `POST /v2/parties`, and the registry flow reaches the ledger, stopping only on
  `Insufficient funds`. See `devnet-findings.md`.
- **The 900s expiry observed live** — token died at t+911s.
- **W3 concurrency** — covered by Furqan's PR #2: 100/100 races with exactly one
  success and one abort, 12/12 attacks rejected for the expected reason.

- **The mandate now moves real Canton Coin.** `ChargeViaTokenStandard` executes
  a real `TransferFactory_Transfer` on Amulet, agent submitting alone with no
  key. Owner −12.0, receiver +12.0, `spent` 12.0 of 50.0, audit record written.
  All three attacks still blocked by the expected rule on real Amulet. See
  `token-standard/`.

### Still open
- Per-period caps (total cap works; per-period is date arithmetic).
- Nothing on DevNet is funded, so the real transfer is LocalNet-only there.
- The owner/agent trust boundary is still in-process in `agent-wallet/`.

### Not blocked — can start now
- **W3 concurrency test.** Two charges racing one mandate; one must abort on
  contention. The sandbox has a real synchronizer, so this no longer needs
  DevNet. **Best remaining differentiator** — arXiv 2602.06345 says this is
  exactly where AP2 implementations fail.
- **W4 narrative + N1.** Untouched all session. Pitch, honesty slide, demo
  script, and N1 as a second submission. Highest score-per-hour on the board,
  needs no code or credentials.
- Move the trust boundary to a real process (HTTP) so the mock disappears.
- Per-period caps — explicitly warned as date-arithmetic-heavy; total cap first.

### Decisions still open
- **The deadline.** Every timing in `context/03-d1-team-plan.md` is a relative
  offset because none has been supplied. The cut list depends on it.
- Whether to send `devnet-findings.md` to Davide. The 900s token finding will
  bite every API-track team; costs nothing competitively.

## 6. Risks

| Risk | State |
|---|---|
| Judges ask for a real token transfer | Not built. Say so first, show the authority proof instead. |
| Judges ask "is this DevNet?" | It is sandbox. Say it before being asked. |
| Demo depends on a live sandbox | Restart takes ~90s; `setup_demo.py` is idempotent and verified from clean state. |
| Someone runs the README cold | Verified: clean-state run is green, exit 0. |
