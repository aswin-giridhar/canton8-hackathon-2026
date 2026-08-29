# W3 — measured results

Generated `2026-08-29T15:41:59.692903+00:00` against `http://localhost:7575`. 
Overall harness verdict: **PASS**.

## Scorecard

| Measurement | Result |
|---|---|
| Attack rules rejected for the expected reason | **12/12** |
| Concurrency runs with exactly 1 success + 1 abort | **100/100** |
| Concurrent submissions | 200 (100 success, 100 contention abort, 0 infrastructure error) |
| Successful-charge latency | p50 **361.4 ms**, p95 **376.7 ms** |
| Sequential charges end-to-end | **100/100** |
| Sequential charge latency | mean **367.9 ms**, p50 **361.0 ms**, p95 **398.2 ms** |
| `daml test --all` | **PASS**, 7.17 s |
| Token refresh | refresh-before-expiry + one retry on 401; concurrent refresh unit-tested |

## Attack matrix

| Attack | Verdict | Ledger reason (compact) | Daml source |
|---|---|---|---|
| unapproved counterparty | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): counterpa...` | `agent-mandate/daml/Mandate.daml:52` — `assertMsg "counterparty is not on the allow-list"` |
| exceed cap | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): charge wo...` | `agent-mandate/daml/Mandate.daml:49` — `assertMsg "charge would exceed the cap" (spent + amount <= cap)` |
| negative amount | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): amount mu...` | `agent-mandate/daml/Mandate.daml:48` — `assertMsg "amount must be positive" (amount > 0.0)` |
| spend after expiry | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): mandate e...` | `agent-mandate/daml/Mandate.daml:47` — `assertMsg "mandate expired" (now < expiresAt)` |
| replay consumed mandate | BLOCKED (expected rule) | `Contract could not be found with id 00439b4e973e99a75fd63f8a567a7e648a0fceffe6851ccc1839d63d76b3135300ca121220ab24e8add8fc2bbeb0b39ea5dbd...` | `agent-mandate/daml/Mandate.daml:36` — `choice Charge : ContractId Mandate` |
| agent raises own cap | BLOCKED (expected rule) | `Interpretation error: Error: node NodeId(0) (6f5c3c9a5f66c4726c62a11bb2f01f9b047097afe6a04ec0674cf5a6e0067f99:Mandate:Mandate) requires a...` | `agent-mandate/daml/Mandate.daml:109` — `controller owner, spender` |
| spend after revocation | BLOCKED (expected rule) | `Contract could not be found with id 0001212cb8092486d5470b7a08408baddd91b519c1f6c2ab0ca3cf070b90b3b2ecca12122060c7aebe7fc42208ca6e6406cb0...` | `agent-mandate/daml/Mandate.daml:81` — `choice Revoke : ()` |
| owner uses spender Charge | BLOCKED (expected rule) | `Interpretation error: Error: node NodeId(0) (6f5c3c9a5f66c4726c62a11bb2f01f9b047097afe6a04ec0674cf5a6e0067f99:Mandate:Mandate) requires a...` | `agent-mandate/daml/Mandate.daml:43` — `controller spender` |
| stranger charges | BLOCKED (expected rule) | `Contract could not be found with id 005f7582f763aa3831aeaedecbbce7e8cccaeae4e0c13fc49f0e3d057b50e85adaca121220428dbdf442b31e0e21ebef90fb4...` | `agent-mandate/daml/Mandate.daml:43` — `controller spender` |
| Restrict widens cap | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): Restrict ...` | `agent-mandate/daml/Mandate.daml:98` — `assertMsg "Restrict may only lower the cap; use Adjust to raise it"` |
| Restrict adds counterparty | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): Restrict ...` | `agent-mandate/daml/Mandate.daml:102` — `assertMsg "Restrict may only remove counterparties; use Adjust to add"` |
| agent invokes owner Restrict | BLOCKED (expected rule) | `Interpretation error: Error: node NodeId(0) (6f5c3c9a5f66c4726c62a11bb2f01f9b047097afe6a04ec0674cf5a6e0067f99:Mandate:Mandate) requires a...` | `agent-mandate/daml/Mandate.daml:96` — `controller owner` |

## Interpretation

Each race submitted two `Charge` exercises against the same immutable Mandate contract id. A consuming choice permits only one transaction to consume that contract; the other submission must abort. The successor mandate is not shared with the losing command, so aggregate spend cannot be lost through a read/check/write race.

The Markdown table compacts errors for readability. `w3-results.json` retains every HTTP error body verbatim, along with per-attempt timings and all concurrency outcomes.

## Scope

These measurements use the project `Purse`/`Mandate` model on a real local Canton sandbox. They do not claim a funded token-standard transfer or a DevNet concurrency result.
