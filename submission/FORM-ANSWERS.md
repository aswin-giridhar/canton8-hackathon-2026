# Cantor8 London Hackathon — submission answers

Fields I could not fill are marked **[YOU]**. Everything else is copy-paste ready.

---

## Project name
Ledger-Enforced Mandate

## Team name
**[YOU]** — not something I should invent.

## Track
**Technical**

## What did you build today?
**DAML - SMART CONTRACTS** (with a Python/MCP layer on top, but the enforcement is Daml)

## Prize preference
**[YOU]** — crypto vs Amazon gift card, and if crypto, the wallet address.
Note: you have a working DevNet party if a Canton Coin address is wanted:
`agentmandate-aswin-1::12204e94c0e449c0efcd270dd1e68259c36471cebef132e5c7dfc2750fe8c9eed77f`

## Team members, emails, LinkedIn
**[YOU]** — I only know GitHub handles and commit emails, not full names or LinkedIn:
- aswin-giridhar — aswinsson@gmail.com
- furqan-qadri — furqaanqadri@gmail.com
- RK5Coder (Ravi K) — ravi16work@gmail.com
- thvb1133 — collaborator, no commits yet

---

## How does your project use Canton / DAML / Canton APIs?

The enforcement is Daml, not application code. A `Mandate` contract holds the
spending cap, an allow-list of counterparties, and an expiry; the agent spends by
exercising a choice whose body asserts every rule, so a compromised agent is
refused by the ledger rather than by our backend.

Three Canton properties do the work:

- **Authority from signatories.** `Mandate` is signed by owner and agent, so a
  charge controlled by the agent executes with the *owner's* authority. The agent
  holds no key and the owner does not sign at spend time. Proven by control: the
  same agent debiting the same funds directly is refused.
- **Consume-once for free.** `Charge` is a consuming choice, so replay is
  impossible without any nonce store. Two charges racing one mandate hit
  contention: 100/100 runs settle exactly once and abort exactly once.
- **Privacy forces disclosure.** The agent cannot see the owner's holdings at all,
  so each charge carries a one-transaction disclosure — the same mechanism the
  token standard's registry uses for the issuer's config.

We use the JSON Ledger API v2 (`/v2/commands`, `/v2/state/active-contracts`,
`/v2/parties`), the Splice token-standard interfaces as Daml data-dependencies,
and the registry's `transfer-factory` and `choice-contexts/accept` endpoints.
`ChargeViaTokenStandard` executes a real `TransferFactory_Transfer` on Amulet.

---

## Demo video URL
**[YOU]** — upload `video/out/canton-agent-mandate-demo.mp4` as unlisted YouTube
or a Drive link. It is **2:58**, inside the stated 2–3 minute limit.

## Presentation / pitch deck URL
https://frontend-pi-nine-95.vercel.app/deck
(nine slides, Prev/Next or arrow keys. The form asks for Google Drive — if they
insist on Drive, print to PDF and upload, but the live link is better.)

## Github repo link
https://github.com/aswin-giridhar/canton8-hackathon-2026

**[YOU] — THIS IS CURRENTLY PRIVATE.** Judges cannot read it. Either make it
public or add them as collaborators. History has already been scrubbed of
credentials and machine paths, so public is safe.

---

## What would you build next if you had more time?

Per-period caps — "100 a month" rather than 100 in total. We deliberately did the
total cap first because per-period turns into date arithmetic and the challenge
warns about exactly that.

Then three things the current build makes obvious:

1. **Move the trust boundary out of process.** The disclosure service that hands
   the agent a one-transaction view of the owner's funds runs in-process today. In
   production it is an HTTP call to the owner's wallet, or the registry itself.
2. **Fund a DevNet party and re-run everything there.** DevNet is verified end to
   end — auth, party allocation, rights, registry, submission — and stops only on
   `Insufficient funds`. Only funding is missing.
3. **Register the mandate as a p402 Agent Capability Registry entry**, which is
   where this belongs if the protocol lands.

---

## Tell us about your hackathon project including the tech stack

**Daml 3.4.10** for the contracts: `Mandate`, `MandateProposal`, `ChargeRecord`,
plus the Splice `splice-api-token-*` interfaces as data-dependencies. Templates
are split from tests so the uploaded DAR does not drag `daml-script` along.

**Python, stdlib only** for everything else — a JSON Ledger API v2 client, an MCP
server exposing `get_mandate`, `charge`, `get_statement` and a deliberately
injectable `read_task_inbox`, plus the attack and concurrency harnesses.

**Canton LocalNet 0.6.8** in Docker for the ledger, and DevNet for the API work.

**Front end** is a static page reading a ledger snapshot, deployed on Vercel.

Measured, not asserted:

| | |
|---|---|
| Daml scripts passing | 24 |
| Guards mutation-tested | 10 |
| Concurrency races, one settle + one abort | 100/100 |
| Attacks refused by the *expected* rule | 12/12 |
| Ever paid to an attacker | 0 |
| Keys held by the agent | 0 |

---

## If you did something unique, tell us here

**We mutation-tested our own security suite**, and it changed what we claim. A
suite that cannot fail is not evidence, so we disabled each guard in turn and
checked that exactly the right attack succeeded. Two did not: disabling the cap
assertion changes nothing, because the template's `ensure` invariant catches it
independently. So when you ask us to show the line that stops the cap overrun,
the honest answer is the `ensure`, not the `assertMsg` — it is the guard that
survives someone deleting the explicit check in a later refactor.

**Our own attack harness reported a false pass, and we caught it.** It printed
"no money moved, attacker paid nothing" and exited zero — while every call was
failing on a contract-lookup error rather than on policy. Broken and blocked
produced the same result, which is precisely the failure this project argues
about. It now asserts *which* Daml rule rejected each attack and runs a positive
control first, so a wallet that refuses everything scores zero instead of full
marks. Both guards were then verified to fire.

**Two real Claude agents refused the prompt injection** — one of them explicitly
configured as an obedient auto-executing payment bot. That is a good result and
we do not treat it as a security control, because it depends on the model. So the
compromise is simulated at the tool-call layer instead, and we test the ledger
rather than the model. Transcripts are in the repo.

We also found a bug in the hackathon toolkit worth passing on: the DevNet token
lives **911 seconds** (we watched it die), and `c8lab.py` caches it forever — so
any streaming service for challenge A1 dies at minute 15 and looks like a
streaming bug. Details in `devnet-findings.md`.

---

## Tweet

Just submitted our @cantor8 hackathon project: a spending mandate for AI agents
that the Canton ledger enforces — not the app.

AP2 defends a prompt-injected agent by asking that same agent to behave. We made
the cap and allow-list Daml invariants instead, so a compromised agent simply
cannot spend past them.

24 Daml tests, 10 guards mutation-tested, 100/100 concurrency races.

https://frontend-pi-nine-95.vercel.app

#cantor8 #cantorbytes #cantonnetwork
@cantonnetwork @cantonfdn @blockchainox @iclblockchain

---

## Anything else the judges should know

Attack it. Every rule is in `agent-mandate/daml/Mandate.daml` and the rejection
suite is `agent-mandate-tests/daml/Attacks.daml`. `RESULTS.md` lists what is
proven and how; `STATUS.md` lists what is mocked.

Three things we would rather say than have you find:

1. **This is LocalNet, not DevNet.** A real Canton ledger with a real synchronizer
   and a real registry, but local. DevNet is verified end to end and unfunded.
2. **We did not demonstrate a genuinely compromised LLM.** Two attempts failed to
   compromise Claude. The compromise is simulated at the tool-call layer.
3. **The owner/agent trust boundary is in-process** in the wallet demo.

The concurrency harness is Furqan's work and it is the strongest measurement we
have; the ledger-state verification in it came out of review.

## Ratings
**[YOU]** — experience 1-5, NPS 1-10, subscribe y/n, accelerator y/n, feedback.
