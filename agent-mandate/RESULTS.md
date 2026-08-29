# Measured results — D1 agent mandate

Everything below was produced by `daml test` on Daml SDK 3.4.10. Reproduce with:

```bash
export PATH="$HOME/.daml/bin:$PATH"
cd agent-mandate && daml test        # ~19s, no node, no network
```

**Count, stated precisely:** 15 scripts run — **12 tests** in `Attacks.daml`, plus
`setupFixture` (a fixture, not a test), plus the starter's `testIou` and
`testMandate`. All pass.

## The rejection suite — 12 tests

| # | Attack or property | Test | Result |
|---|---|---|---|
| 1 | pays a counterparty not on the allow-list | `attack_paysUnapprovedCounterparty` | rejected on-ledger |
| 2 | spends more than the cap | `attack_exceedsCap` | rejected |
| 3 | negative amount, to run the cap backwards | `attack_negativeAmountToInflateHeadroom` | rejected |
| 4 | spends after expiry | `attack_spendsAfterExpiry` | rejected |
| 5 | replays a charge (consume-once) | `attack_replaysTheSameCharge` | rejected |
| 6 | agent raises its own cap | `attack_agentRaisesOwnCap` | rejected |
| 7 | spends after revocation | `attack_spendsAfterRevocation` | rejected |
| 8 | owner charges via the spender's choice | `attack_ownerChargesViaSpendersChoice` | rejected |
| 9 | unrelated third party charges | `attack_strangerCharges` | rejected |
| 10 | **positive control** — a legitimate charge succeeds | `audit_chargeLeavesReadableRecord` | passes |
| 11 | audit trail outlives revocation | `audit_survivesRevocation` | passes |
| 12 | empty allow-list means the agent can pay nobody | `property_emptyAllowListPaysNobody` | passes |

Test 10 is load-bearing for the whole suite: a set of `submitMustFail` assertions
passes trivially if charges never work at all. It can only pass if a legitimate
charge *succeeds*, which is what proves the allow-list rejects Mallory
specifically rather than rejecting everyone.

## Mutation testing — does the suite actually discriminate?

A rejection suite that cannot fail is not evidence. Each guard was disabled in
turn and the suite re-run. Seven guards tested.

| Guard disabled | Attack that then succeeds | Verdict |
|---|---|---|
| `assertMsg "mandate expired"` | `attack_spendsAfterExpiry` | **sole guard** |
| allow-list `elem` check | `attack_paysUnapprovedCounterparty` | **sole guard** |
| `assertMsg "charge would exceed the cap"` | *(none)* | double-guarded |
| `assertMsg "amount must be positive"` | *(none)* | double-guarded |
| `Charge` made non-consuming | `attack_replaysTheSameCharge` | **sole guard** |
| `Revoke` made non-consuming | `attack_spendsAfterRevocation`, `testMandate` | **sole guard** |
| `Adjust` controllable by spender alone | `attack_agentRaisesOwnCap`, `testMandate` | **sole guard** |

### Two rules are double-guarded — worth knowing which line does the work

Disabling the cap or positivity `assertMsg` changes nothing, because the template
invariant catches both independently:

```daml
ensure cap > 0.0 && spent >= 0.0 && spent <= cap
```

`ensure` is checked on **every create, forever** — you cannot forget it in a new
choice. Confirmed by double mutation:

```
disable cap assertMsg + ensure        -> attack_exceedsCap SUCCEEDS
disable positivity assertMsg + ensure -> attack_negativeAmountToInflateHeadroom SUCCEEDS
```

**So when asked "show us the line that stops it", the honest answer for the cap is
the `ensure`, not the `assertMsg`** — it is the guard that survives someone
deleting the explicit check in a later refactor. The allow-list, expiry, and all
three structural guards are each a single point of failure by contrast.

### The consume-once result is the one that matters for the pitch

`Charge` made non-consuming → `attack_replaysTheSameCharge` succeeds. That is the
claim the whole AP2 comparison rests on, and it is now measured rather than
asserted: consume-once here is not a policy anyone enforces, it is what a
consuming choice *is*. arXiv 2602.06345 had to add a runtime verifier with
time-bound nonces to get the same property.

### One mutation that does not cleanly isolate — stated rather than hidden

Changing `Charge`'s controller from `spender` to `owner` makes
`attack_ownerChargesViaSpendersChoice` fail (so the test does discriminate), but
it also fails 4 other tests, because legitimate agent charges break at the same
time. Authorization direction cannot be mutated in isolation this way. The test
is real; the mutation is not a clean single-variable experiment, and we are not
claiming it is.

## A metric we are deliberately not headlining — and the real gap inside it

Daml's choice coverage went **50% → 45.5%** across this work. Two separate things
are tangled in that number, and only one of them is a metric artefact:

- **Artefact:** adding `ChargeRecord` added an unexercised `Archive` choice to the
  denominator, and `submitMustFail` does not count as exercising a choice — so all
  nine attack tests contribute zero. Coverage understates the attack suite.
- **A real gap, not an artefact:** `MandateProposal.Reject` and `Iou.Split` still
  have **no successful-path test at all.** That is genuinely untested behaviour and
  coverage is right to flag it.

Mutation coverage is the better instrument for the security suite. It does not
excuse the two untested choices.

## Design decisions worth stating

- **The allow-list cannot be changed after acceptance.** `Adjust` changes the cap
  only. An owner who wants to remove a counterparty must `Revoke` and re-propose.
  Deliberate — a mutable allow-list on a live mandate is another attack surface —
  but it is a choice, not an oversight.
- **`ChargeRecord` is signed by owner and spender and is never archived by any
  choice**, so neither party can rewrite history alone and revocation cannot erase
  the trail (test 11).
- **The audit record is written in the same transaction as the spend**, so "charged
  without an audit entry" is not a state the ledger can reach.

## Not built

Stated plainly, because overclaiming is penalised harder than an incomplete build.

- **No value moves.** `Charge` records the spend and writes the audit entry; it
  does **not** exercise a token-standard transfer. This is the largest gap.
- **Nothing has run against DevNet.** `daml test` is in-memory. No party has been
  allocated, and party allocation on DevNet is documented as unverified.
- **No concurrency test.** Two charges racing one mandate should see one abort on
  contention. This *cannot* run under `daml test` — the script runtime is
  sequential — so it needs a real ledger and a party we can submit as.
- No MCP server, no agent, no prompt-injection demo yet.
