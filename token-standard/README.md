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

## What this does NOT yet do

The `Mandate` contract still debits the local `Purse` template, not Amulet.
Wiring `Charge` to exercise `TransferFactory_Transfer` is the remaining
integration: it needs our DAR uploaded to LocalNet and the Splice token-standard
interfaces as Daml dependencies. **The transfer works and the mandate works;
they are not yet joined.**
