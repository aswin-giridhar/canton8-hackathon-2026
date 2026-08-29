# The approved-supplier list is the secret

## What you can build on Canton that you cannot build on Ethereum

**Cantor8 London Hackathon 2026 · Non-technical track (N1)**

---

## The claim in one sentence

You can give an autonomous agent spending authority that **every counterparty can
rely on and no counterparty can read**. On a public chain those two properties are
mutually exclusive, because the only way to let a merchant verify a limit is to
publish it.

---

## The use case, named

A listed pharmaceutical company — call it **Meridian Therapeutics** — runs an AI
procurement agent that buys **spot manufacturing capacity from contract
manufacturing organisations (CMOs)**.

When a batch fails quality control or a launch date pulls forward, Meridian needs
fill-finish capacity within days. Today a human buyer phones three CMOs, gets
quotes, and raises a purchase order. The agent's job is to do that continuously:
monitor batch yields, and when capacity is needed, buy it from a pre-approved CMO
within a budget the treasury team set.

The parties are real and specific:

- **Meridian Treasury** — sets the budget, owns the money
- **Meridian's procurement agent** — an AI agent, spends within the mandate
- **Lonza, Catalent, Recipharm** — three approved CMOs, mutual competitors
- **Meridian's statutory auditor** — must reconstruct every purchase afterwards

---

## What breaks today

**The CMO cannot verify the agent's authority.** Meridian's mandate lives in its
ERP. When the agent commits to a €400,000 booking, Lonza has no way to check that
it was authorised — Lonza is being asked to take Meridian's own system's word for
it. In practice this is patched with a phone call to a named buyer, which is
exactly the step an autonomous agent is supposed to remove.

**Why not just a database?** Because a database has an owner, and here nobody
will accept the other side's. Meridian will not give Lonza a login to its
procurement system, and Lonza will not treat a webhook from Meridian's ERP as
proof of anything — the counterparty controls it and can rewrite it. Two firms
that compete for the same molecules do not share a schema. This is not a
single-owner problem, so Postgres is the wrong answer.

**Why hasn't a public chain solved it?** Because of what the mandate contains.

To let Lonza verify "this agent may spend up to €2m, with these counterparties,
until 31 March", the mandate has to be readable by Lonza. On Ethereum that means
readable by everyone. And **the approved-CMO list is the drug pipeline.**

Consider what a competitor learns from a public mandate:

- Meridian approved a **sterile injectable** CMO last week → an injectable is
  moving to commercial scale
- The cap rose from €400k to €2m → a launch, not a trial batch
- The list includes a **high-potency API** specialist → oncology
- Spend against the cap is accelerating in Q3 → the launch date

None of that is disclosed today. For a listed company it is price-sensitive.
Publishing the mandate to make it verifiable would leak the thing the mandate is
for. And Lonza would see that Catalent is also approved, and roughly what
Meridian is prepared to pay — which is Lonza's negotiating position, handed over.

So the requirement is genuinely awkward: **the mandate must bind everyone and be
legible to no one.**

---

## Which Canton property does the work

Both, and they are separable.

**Privacy — enforcement without disclosure.** On Canton a contract is visible
only to its stakeholders. The `Mandate` is signed by Meridian Treasury and the
agent; the CMOs are not parties to it and never see it. When the agent buys from
Lonza, Lonza becomes a stakeholder on *that booking* and nothing else. The cap
constrains all three CMOs and is legible to none of them.

This is the part that has no Ethereum equivalent. Not "harder" — structurally
absent. A public chain can hide values behind commitments or zero-knowledge
proofs, but then the CMO must trust a proving system and an off-chain prover, and
the counterparty set itself still leaks through the transaction graph.

**Atomic settlement across organisations that do not trust each other.** The
booking, the payment, and the audit record commit in one transaction across
Meridian's validator and Lonza's. There is no window in which Lonza has confirmed
capacity but not been paid, or Meridian has paid for capacity not reserved. And
because the mandate contract is *consumed* by the charge, the same authorisation
cannot be spent twice — even if the agent is compromised and retries.

### Who sees what, party by party

| | Mandate terms (cap, allow-list, expiry) | Meridian↔Lonza booking | Meridian↔Catalent booking | Running total spent |
|---|---|---|---|---|
| **Meridian Treasury** | yes — signatory | yes | yes | yes |
| **Procurement agent** | yes — signatory | yes | yes | yes |
| **Lonza** | **no** | yes — stakeholder | **no** | **no** |
| **Catalent** | **no** | **no** | yes — stakeholder | **no** |
| **Recipharm** (approved, unused) | **no** | **no** | **no** | **no** |
| **Auditor** | yes — observer | yes | yes | yes |
| **Everyone else** | **no** | **no** | **no** | **no** |

Naming the exclusions precisely: **Lonza cannot see that Catalent is approved.**
Recipharm cannot tell it is on the list at all. No CMO learns the cap, the
remaining budget, or the rate of spend. A competitor with a Canton node sees
nothing whatsoever.

---

## The flow

1. **Meridian Treasury proposes** a mandate: €2m cap, allow-list of the three
   CMOs, expiring 31 March. Signed by Treasury.
2. **The agent accepts.** Both are now signatories; the contract exists and binds
   both. Neither can be enrolled without consenting.
3. **A batch fails.** The agent needs 40,000 vials of fill-finish capacity.
4. **The agent commits to Lonza.** It exercises a charge on the mandate. The
   ledger checks — not Meridian's server — that Lonza is on the allow-list, that
   €400k is within the remaining cap, and that the mandate has not expired or
   been revoked. Lonza's node sees a booking it is party to, and can rely on it
   without seeing the mandate.
5. **Atomically, in the same transaction:** the booking is created, payment
   settles, the mandate is consumed and replaced with one recording €400k spent,
   and an audit record is written naming which rule permitted the charge.
6. **Something goes wrong.** A CMO is placed under an FDA consent decree.
   Treasury removes it from the allow-list unilaterally — the agent cannot block
   or delay this, and the other two CMOs are unaffected. The mandate survives;
   only its scope narrows.
7. **Year end.** The auditor, an observer throughout, reconstructs every purchase
   and the rule that authorised it. No party had to be asked for records.

---

## What you are still trusting

Canton is not trustless, and pretending otherwise would be the easiest way to
lose this argument.

**The synchronizer operators.** The global synchronizer is run by a vetted set of
organisations. They cannot read transaction contents, but they order and confirm
them, and they could in principle censor. Meridian is trusting a named consortium
not to, and has contractual recourse rather than cryptographic guarantees.

**Your validator operator.** Unless Meridian runs its own node, whoever hosts its
party can see everything that party can see. That is an outsourcing decision with
the same shape as custody.

**The token issuer.** Whatever settles the payment — Canton Coin or a tokenised
deposit — has a named legal entity behind it. If that issuer freezes, fails, or
is compelled by a court, the ledger's guarantees do not save you.

**The CMO's real-world performance.** The ledger proves the booking was
authorised and paid. It cannot prove vials were filled. Every on-chain system
terminates in an off-chain promise.

**And the cost of the privacy itself.** You cannot audit Canton the way you audit
Ethereum. On Ethereum, anyone can re-derive total supply and every balance from
public data. On Canton you see only your own slice — you cannot independently
verify that the issuer has not minted quietly, or that some other party's
mandate has not been abused. You trade *universal verifiability* for
*confidentiality*, and you get selective disclosure to a regulator instead of
open inspection by anyone.

That is a real loss. For a pharmaceutical procurement desk it is obviously the
right trade, because the thing being protected is the pipeline and the alternative
is not being able to use the system at all. For a permissionless DeFi protocol it
would obviously be the wrong one. The point is that it is a *choice*, and Canton
is the system that lets you make it.

---

## Why this is the difference between possible and impossible

Strip either property away and the use case collapses.

**Without privacy** Meridian will not do it, because the mandate discloses the
pipeline and the negotiating position. Legal will stop it before procurement
does.

**Without atomic cross-organisation settlement** the CMOs will not do it, because
they are back to trusting Meridian's ERP — and a shared ledger that still requires
you to trust the counterparty's system has bought you nothing.

Only the combination makes an autonomous procurement agent something a listed
pharmaceutical company could actually deploy. That combination is what Canton
provides and Ethereum, by construction, does not.

---

*Companion technical build: a spending mandate enforced in Daml, with the cap,
allow-list, expiry and revocation as ledger invariants rather than backend checks.
24 Daml scripts, 10 guards mutation-tested, 100/100 concurrency races.*
