# W3 — measured results

Generated `2026-08-29T16:22:18.715411+00:00` against `http://localhost:7575`.
Overall harness verdict: **PASS**.

## Scorecard

| Measurement | Result |
|---|---|
| Attack rules rejected for the expected reason | **12/12** |
| Concurrency runs with exactly 1 success + 1 abort | **100/100** |
| Concurrency runs verified from ledger state | **100/100** |
| Concurrent submissions | 200 (100 success, 100 contention abort, 0 infrastructure error) |
| Successful-charge latency | p50 **342.7 ms**, p95 **419.5 ms** |
| Sequential charges end-to-end | **100/100** |
| Sequential charge latency | mean **363.3 ms**, p50 **360.7 ms**, p95 **380.0 ms** |
| `daml test --all` | **PASS**, 7.27 s |
| Token refresh | refresh-before-expiry + one retry on 401; concurrent refresh unit-tested |

## Attack matrix

| Attack | Verdict | Ledger reason (compact) | Daml source |
|---|---|---|---|
| unapproved counterparty | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): counterpa...` | `agent-mandate/daml/Mandate.daml:52` — `assertMsg "counterparty is not on the allow-list"` |
| exceed cap | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): charge wo...` | `agent-mandate/daml/Mandate.daml:49` — `assertMsg "charge would exceed the cap" (spent + amount <= cap)` |
| negative amount | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): amount mu...` | `agent-mandate/daml/Mandate.daml:48` — `assertMsg "amount must be positive" (amount > 0.0)` |
| spend after expiry | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): mandate e...` | `agent-mandate/daml/Mandate.daml:47` — `assertMsg "mandate expired" (now < expiresAt)` |
| replay consumed mandate | BLOCKED (expected rule) | `Contract could not be found with id 00f88224678153ef5d93dee57a2032e68cb675c1b1715da466f02715c95642dd69ca1212203a01f947d4b48f0ebd21e3338c4...` | `agent-mandate/daml/Mandate.daml:36` — `choice Charge : ContractId Mandate` |
| agent raises own cap | BLOCKED (expected rule) | `Interpretation error: Error: node NodeId(0) (6f5c3c9a5f66c4726c62a11bb2f01f9b047097afe6a04ec0674cf5a6e0067f99:Mandate:Mandate) requires a...` | `agent-mandate/daml/Mandate.daml:109` — `controller owner, spender` |
| spend after revocation | BLOCKED (expected rule) | `Contract could not be found with id 003271aac8ffb0981795ee5a276d059f3f441c312bbf0483499fa29f60f70dfc9eca1212201f56362d92f669c11c09180e1be...` | `agent-mandate/daml/Mandate.daml:81` — `choice Revoke : ()` |
| owner uses spender Charge | BLOCKED (expected rule) | `Interpretation error: Error: node NodeId(0) (6f5c3c9a5f66c4726c62a11bb2f01f9b047097afe6a04ec0674cf5a6e0067f99:Mandate:Mandate) requires a...` | `agent-mandate/daml/Mandate.daml:43` — `controller spender` |
| stranger charges | BLOCKED (expected rule) | `Contract could not be found with id 00ba71d3761ba5c533c35d8fe4f7c4240fca53078b98cad6616cba1deb649506ecca121220a3e26e69f6d14da48863ac525d1...` | `agent-mandate/daml/Mandate.daml:43` — `controller spender` |
| Restrict widens cap | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): Restrict ...` | `agent-mandate/daml/Mandate.daml:98` — `assertMsg "Restrict may only lower the cap; use Adjust to raise it"` |
| Restrict adds counterparty | BLOCKED (expected rule) | `Interpretation error: Error: User failure: UNHANDLED_EXCEPTION/DA.Exception.AssertionFailed:AssertionFailed (error category 9): Restrict ...` | `agent-mandate/daml/Mandate.daml:102` — `assertMsg "Restrict may only remove counterparties; use Adjust to add"` |
| agent invokes owner Restrict | BLOCKED (expected rule) | `Interpretation error: Error: node NodeId(0) (6f5c3c9a5f66c4726c62a11bb2f01f9b047097afe6a04ec0674cf5a6e0067f99:Mandate:Mandate) requires a...` | `agent-mandate/daml/Mandate.daml:96` — `controller owner` |

## Interpretation

Each race submitted two `Charge` exercises against the same immutable Mandate contract id. A consuming choice permits only one transaction to consume that contract; the other submission must abort. After every race the harness queried the active contract set and verified that the original mandate was consumed, exactly one successor was created, and its `spent` field was `1.0`. The verdict therefore depends on committed ledger state, not only HTTP responses.

The Markdown table compacts errors for readability. `w3-results.json` retains every HTTP error body verbatim, along with per-attempt timings and all concurrency outcomes.

## Scope

These measurements use the project `Purse`/`Mandate` model on a real local Canton sandbox. They do not claim a funded token-standard transfer or a DevNet concurrency result.
