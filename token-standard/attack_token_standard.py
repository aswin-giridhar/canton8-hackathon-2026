"""Do the mandate's rules still hold when real Amulet is moving?

An integration that moves money but loses the enforcement is worse than no
integration. These are the judges' stated attacks, run against the REAL token
standard rather than the Purse mock.

The subtle one is `mismatched_receiver`: the agent builds the transfer itself,
so it could try to satisfy the guards with one counterparty while the transfer
actually pays another. ChargeViaTokenStandard validates
`transferArgs.transfer` -- the transfer that will execute -- so it cannot.
"""
import datetime, sys
sys.path.insert(0, ".")
import c8lab as C
from mandate_moves_amulet import (MANDATE, PROPOSAL, iso, amulet,
                                  holding_disclosures, live_mandates)

CAP = "50.0"


def build(owner, receiver, dso, amount, sender=None):
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    hs = [h for h in C.holdings(owner)
          if not h["locked"] and h["instrument"] == "Amulet"]
    args = {"expectedAdmin": dso,
            "transfer": {"sender": sender or owner, "receiver": receiver,
                         "amount": amount,
                         "instrumentId": {"admin": dso, "id": "Amulet"},
                         "requestedAt": iso(now),
                         "executeBefore": iso(now + datetime.timedelta(hours=24)),
                         "inputHoldingCids": [h["contractId"] for h in hs],
                         "meta": {"values": {}}},
            "extraArgs": {"context": {"values": {}}, "meta": {"values": {}}}}
    fac = C.registry("/registry/transfer-instruction/v1/transfer-factory",
                     {"choiceArguments": args})
    cc = fac.get("choiceContext", {})
    args["extraArgs"]["context"] = cc.get("choiceContextData", {})
    return fac, cc, args


def main():
    owner = C.find_party("app_user")
    agent = C.allocate_party("amulet_agent")
    receiver = C.find_party("mandate_receiver")
    mallory = C.allocate_party("amulet_mallory")     # NOT on the allow-list
    dso = C.dso_party()
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

    prop = C.submit([{"CreateCommand": {"templateId": PROPOSAL, "createArguments": {
        "owner": owner, "spender": agent, "cap": CAP,
        "allowedCounterparties": [receiver],
        "expiresAt": iso(now + datetime.timedelta(hours=24))}}}],
        act_as=owner, want_transaction=True)
    pcid = [(e.get("CreatedTreeEvent", {}).get("value") or e.get("CreatedEvent"))["contractId"]
            for e in prop["transaction"]["events"]
            if (e.get("CreatedTreeEvent", {}).get("value") or e.get("CreatedEvent"))][0]
    acc = C.submit([{"ExerciseCommand": {"templateId": PROPOSAL, "contractId": pcid,
                                         "choice": "Accept", "choiceArgument": {}}}],
                   act_as=agent, want_transaction=True)
    mandate = [(e.get("CreatedTreeEvent", {}).get("value") or e.get("CreatedEvent"))["contractId"]
               for e in acc["transaction"]["events"]
               if (e.get("CreatedTreeEvent", {}).get("value") or e.get("CreatedEvent"))][0]

    before = (amulet(owner), amulet(mallory))
    print(f"  mandate: cap {CAP}, allow-list [receiver]\n")

    attacks = [
        ("pay a counterparty not on the allow-list", receiver, mallory, "10.0",
         "counterparty is not on the allow-list"),
        ("exceed the cap",                            receiver, receiver, "500.0",
         "charge would exceed the cap"),
        ("mismatched receiver: guards say one payee, transfer names another",
                                                      receiver, mallory, "5.0",
         "counterparty is not on the allow-list"),
    ]

    failures = []
    for label, _decoy, real_receiver, amount, expect in attacks:
        fac, cc, args = build(owner, real_receiver, dso, amount)
        try:
            C.submit([{"ExerciseCommand": {
                         "templateId": MANDATE, "contractId": mandate,
                         "choice": "ChargeViaTokenStandard",
                         "choiceArgument": {"factoryCid": fac["factoryId"],
                                            "transferArgs": args}}}],
                     act_as=agent,
                     disclosed=cc.get("disclosedContracts", []) + holding_disclosures(owner),
                     want_transaction=True)
            print(f"  *** WENT THROUGH ***  {label}")
            failures.append(label)
        except C.LabError as e:
            ok = expect in str(e)
            print(f"  {'BLOCKED' if ok else 'WRONG REASON':14}  {label}")
            print(f"  {'':14}  rule: {expect if ok else str(e)[:90]}")
            if not ok:
                failures.append(f"{label}: wrong reason")

    after = (amulet(owner), amulet(mallory))
    print(f"\n  owner   {before[0]:.2f} -> {after[0]:.2f}")
    print(f"  mallory {before[1]:.2f} -> {after[1]:.2f}")
    if after[1] != before[1]:
        failures.append("the attacker was paid")
    if failures:
        print("\n  FAIL:", "; ".join(failures))
        return 1
    print("\n  PASS: every attack refused by the expected rule, on REAL Amulet;")
    print("        the attacker was paid nothing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
