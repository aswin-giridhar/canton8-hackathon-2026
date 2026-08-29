# Measured results — D1 agent mandate

All numbers produced by `daml test` on SDK 3.4.10. Reproduce with:

```bash
export PATH="$HOME/.daml/bin:$PATH"
cd agent-mandate && daml test
```

## The rejection suite

12 scripts, all passing, ~19s, no node and no network.

| Attack | Test | Result |
|---|---|---|
| pays a counterparty not on the allow-list | `attack_paysUnapprovedCounterparty` | rejected on-ledger |
| spends more than the cap | `attack_exceedsCap` | rejected |
| negative amount, to run the cap backwards | `attack_negativeAmountToInflateHeadroom` | rejected |
| spends after expiry | `attack_spendsAfterExpiry` | rejected |
| replays a charge (consume-once) | `attack_replaysTheSameCharge` | rejected |
| agent raises its own cap | `attack_agentRaisesOwnCap` | rejected |
| spends after revocation | `attack_spendsAfterRevocation` | rejected |
| **positive control** — legitimate charge succeeds | `audit_chargeLeavesReadableRecord` | passes |
| audit trail outlives revocation | `audit_survivesRevocation` | passes |

The positive control matters: a suite made only of `submitMustFail` passes
trivially if charges never work at all. That test can only pass if a legitimate
charge succeeds, which is what proves the allow-list rejects Mallory
specifically rather than rejecting everyone.

## Mutation testing — does the suite actually discriminate?

A rejection suite that cannot fail is not evidence. Each guard was disabled in
turn (condition replaced with `True`) and the suite re-run.

| Guard disabled | Attack that then succeeds | Verdict |
|---|---|---|
| `assertMsg "mandate expired"` | `attack_spendsAfterExpiry` | guard is load-bearing |
| allow-list `elem` check | `attack_paysUnapprovedCounterparty` | guard is load-bearing |
| `assertMsg "charge would exceed the cap"` | *(none)* | **double-guarded** |
| `assertMsg "amount must be positive"` | *(none)* | **double-guarded** |

The last two are caught a second time by the template invariant
`ensure cap > 0.0 && spent >= 0.0 && spent <= cap`, which is checked on **every
create, forever**. Confirmed by double mutation — disabling the `assertMsg` *and*
the `ensure` together is what lets the attack through:

```
disable cap assertMsg + ensure        -> attack_exceedsCap SUCCEEDS
disable positivity assertMsg + ensure -> attack_negativeAmountToInflateHeadroom SUCCEEDS
```

**So when asked "show us the line that stops it", the honest answer for the cap is
the `ensure`, not the `assertMsg`** — the `ensure` is the one that survives someone
deleting the explicit check in a later refactor.

## A metric we are deliberately not reporting

Daml's own choice coverage went **50% → 45.5%** across this work. That is not a
regression: adding the `ChargeRecord` template added an unexercised `Archive`
choice to the denominator, and `submitMustFail` does not count as exercising a
choice — so all seven attack tests contribute zero to it.

Choice coverage is the wrong instrument for a security suite. Mutation coverage
is the right one, which is why the table above exists.

## Not yet done

- No value moves. `Charge` records the spend and writes the audit entry; it does
  not yet exercise a token-standard transfer. **This part is not built.**
- Not run against DevNet — `daml test` is in-memory. No party has been allocated.
- No concurrency test yet. Two charges racing one mandate should see one abort on
  contention; that needs a real ledger, not the script runtime.
