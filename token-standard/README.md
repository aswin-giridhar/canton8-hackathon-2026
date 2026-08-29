# A real token-standard transfer, settled

This is **not** the `Purse` mock in `agent-wallet/`. It is real Canton Coin
(Amulet), the real Splice registry, real disclosed contracts, and the real
two-phase `TransferFactory` flow — on a LocalNet that minted the coin itself.

This was the largest gap in the project. It is now closed.

## Run it

Start LocalNet (see `../LOCALNET.md`), wait for a mining round to pay the
validator, then:

```bash
cd hackathon-toolkit
python3 ../token-standard/real_transfer.py
```

## Measured output

```
BEFORE
  sender       2485.16  (1 holding(s))
  receiver       25.00  (1 holding(s))

PHASE 1  transferKind=offer, 4 disclosed,
         context=['open-round', 'external-party-config-state', 'amulet-rules']
PHASE 2  submitted; instruction=00c51f899f8da9ab9b471226...

AFTER SUBMIT (not yet accepted)
  sender       2485.16  (2 holding(s), 25.0 locked)
  receiver       25.00  (1 holding(s))

PHASE 3  accepted by the receiver

FINAL (read back from the ledger)
  sender       2460.16  (1 holding(s))
  receiver       50.00  (2 holding(s))

receiver gained 25.0, sender paid 25.0, no funds left locked: True
RESULT: real token-standard transfer settled ✓
```

Reproducible: a second run moved another 25.0 correctly, exit 0.

## The three things this demonstrates

**Privacy forces the two-phase flow.** You cannot see the issuer's
configuration contracts, so the registry hands them over as **disclosed
contracts** valid for one transaction. Here that was 4 contracts plus a context
naming `amulet-rules`, `open-round` and `external-party-config-state`. A
hand-built transfer cannot work — not because the API is awkward, but because
you are not allowed to see what it needs.

**`transferKind` decides whether money actually moved.** The receiver had no
`TransferPreapproval`, so the registry answered `offer`. The submission
**succeeded** and the receiver still had nothing — the sender's 25.0 sat
**locked**, escrowed against the offer, until the receiver accepted. A caller
that trusts the success response concludes the money arrived. It has not.

**Locked holdings are not spendable.** Mid-flow the sender showed 2 holdings
with 25.0 locked. Passing a locked holding as a transfer input fails with an
error about `Lock.expiresAt` that says nothing about locks being the problem.

## Verification stance

Every balance is **read back from the ledger**. The transfer's own success
response is never treated as evidence — which is precisely the failure the
`offer` case produces, and the same discipline that caught the false pass in
`agent-wallet/compromised_agent.py`.

## The mandate now moves real Canton Coin

The two halves are joined. `ChargeViaTokenStandard` executes a real
`TransferFactory_Transfer` on Amulet, with the ledger enforcing the cap and
allow-list **on the transfer that actually runs**.

```bash
cd agent-mandate && daml build
daml ledger upload-dar --host localhost --port 2901 \
  --access-token-file <token> .daml/dist/agent-mandate-0.0.1.dar

cd hackathon-toolkit
python3 ../token-standard/mandate_moves_amulet.py
python3 ../token-standard/attack_token_standard.py
```

```
owner    app_user   (3576.16 Amulet)
agent    amulet_agent  (holds no coin, holds no key)
mandate  cap 50.0, allow-list [receiver], spender=agent

registry transferKind=offer, 4 issuer-config disclosures
owner discloses 1 holding(s) for this one transaction
agent exercised ChargeViaTokenStandard ALONE -> offer 00c0daf5...
receiver accepted

owner    3576.16 -> 3564.16
receiver   74.00 ->   86.00
mandate spent = 12.0 of 50.0
audit: 12.0 to receiver | token standard transfer within cap (12.0 of 50.0)
       to an allow-listed counterparty

RESULT: the mandate moved REAL Canton Coin ✓
```

**The agent submitted alone.** It holds no key and the owner did not sign at
spend time — the Mandate carries the owner's authority because the owner is a
signatory on it. That claim was proven earlier against our own `Purse`; this is
the same mechanism against real Amulet and the real registry.

### The enforcement survived the integration

An integration that moves money but loses the rules is worse than none.
`attack_token_standard.py`, against real Amulet:

```
BLOCKED  pay a counterparty not on the allow-list
         rule: counterparty is not on the allow-list
BLOCKED  exceed the cap
         rule: charge would exceed the cap
BLOCKED  mismatched receiver: guards say one payee, transfer names another
         rule: counterparty is not on the allow-list

owner   3564.16 -> 3564.16      mallory 0.00 -> 0.00
PASS: every attack refused by the expected rule, on REAL Amulet.
```

### The design decision that makes it safe

The agent builds the transfer itself, so it could try to satisfy the guards with
one counterparty while the transfer pays another. Every rule is therefore checked
against **`transferArgs.transfer`** — the transfer that will execute — never
against separate parameters:

```daml
let t = transferArgs.transfer
assertMsg "transfer sender must be the mandate owner" (t.sender == owner)
validateCharge owner allowedCounterparties cap spent expiresAt
               t.amount t.receiver now
```

`validateCharge` is a single shared function used by both charge paths. Two
paths with two copies of the rules is how guards drift apart.

### Two things this cost us to learn

**The agent cannot see the owner's coin.** Submitting without disclosing the
owner's holdings fails with `CONTRACT_NOT_FOUND` on the input holding — which
reads like a stale contract and is actually the privacy model. Each charge
carries a fresh, one-transaction disclosure; the agent never gets standing
sight of the owner's funds. Same gate we hit with `Purse`.

**`TransferInstruction` is an interface, not a template.** A `TemplateFilter`
returns `NO_TEMPLATES_FOR_PACKAGE_NAME`, and the tree from `submit-and-wait`
does not surface the created instruction either. It must be found with an
`InterfaceFilter` — and by **set-diff against a pre-submission snapshot**, not
"the first pending offer". Taking the first one once accepted a leftover from
an earlier run and reported success: the net numbers looked right and the
causality was wrong.
