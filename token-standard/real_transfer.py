"""A real Canton Coin transfer through the token standard, end to end.

Not our Purse mock: real Amulet, the real Splice registry, real disclosed
contracts, and the real two-phase TransferFactory flow, against a LocalNet
that minted the coin itself.

Run LocalNet first (see ../LOCALNET.md), then:

    cd hackathon-toolkit && python3 ../token-standard/real_transfer.py

Every balance below is read back from the ledger. The transfer's own success
response is not treated as evidence -- an `offer` returns success while moving
no money at all, which is the single most common confusion on this API.
"""
import datetime, json, sys
sys.path.insert(0, ".")
import c8lab as C

AMOUNT = "25.0"


def balances(*parties):
    out = {}
    for name, p in parties:
        h = C.holdings(p)
        out[name] = {"total": sum(float(x["amount"]) for x in h),
                     "locked": sum(float(x["amount"]) for x in h if x["locked"]),
                     "count": len(h)}
    return out


def show(label, b):
    print(f"  {label}")
    for name, v in b.items():
        lock = f", {v['locked']} locked" if v["locked"] else ""
        print(f"    {name:9} {v['total']:>10.2f}  ({v['count']} holding(s){lock})")


def main():
    sender = C.find_party("app_user")
    receiver = C.allocate_party("mandate_receiver")
    dso = C.dso_party()

    spendable = [h for h in C.holdings(sender)
                 if not h["locked"] and h["instrument"] == "Amulet"]
    if not spendable:
        raise SystemExit("sender has no spendable Amulet; wait for a mining round")

    before = balances(("sender", sender), ("receiver", receiver))
    show("BEFORE", before)

    t0 = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    args = {"expectedAdmin": dso,
            "transfer": {"sender": sender, "receiver": receiver,
                         "amount": AMOUNT,
                         "instrumentId": {"admin": dso, "id": "Amulet"},
                         "requestedAt": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "executeBefore": (t0 + datetime.timedelta(hours=24)
                                           ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "inputHoldingCids": [h["contractId"] for h in spendable],
                         "meta": {"values": {}}},
            "extraArgs": {"context": {"values": {}}, "meta": {"values": {}}}}

    # PHASE 1 -- the registry hands over the issuer's config as disclosed
    # contracts. You cannot see them yourself; that is the privacy model, and
    # it is why a hand-built transfer cannot work.
    fac = C.registry("/registry/transfer-instruction/v1/transfer-factory",
                     {"choiceArguments": args})
    cc = fac.get("choiceContext", {})
    kind = fac.get("transferKind")
    print(f"\n  PHASE 1  transferKind={kind}, "
          f"{len(cc.get('disclosedContracts', []))} disclosed, "
          f"context={list((cc.get('choiceContextData') or {}).get('values', {}))}")

    # PHASE 2 -- exercise the factory with that context attached.
    args["extraArgs"]["context"] = cc.get("choiceContextData", {})
    res = C.submit([{"ExerciseCommand": {
                       "templateId": C.TRANSFER_FACTORY,
                       "contractId": fac["factoryId"],
                       "choice": "TransferFactory_Transfer",
                       "choiceArgument": args}}],
                   act_as=sender, disclosed=cc.get("disclosedContracts", []),
                   want_transaction=True)
    instruction = C._find_instruction_cid(res)
    print(f"  PHASE 2  submitted; instruction={(instruction or '(direct)')[:24]}...")

    mid = balances(("sender", sender), ("receiver", receiver))
    show("\n  AFTER SUBMIT (not yet accepted)", mid)
    if kind == "offer":
        print("    ^ the receiver still has nothing. The sender's funds are LOCKED,")
        print("      escrowed against the offer. This is what `offer` means.")

    # PHASE 3 -- an offer must be accepted before value moves.
    if kind == "offer" and instruction:
        ctx = C.registry(f"/registry/transfer-instruction/v1/{instruction}"
                         "/choice-contexts/accept", {"meta": {}})   # FLAT meta
        C.submit([{"ExerciseCommand": {
                     "templateId": C.TRANSFER_INSTRUCTION,
                     "contractId": instruction,
                     "choice": "TransferInstruction_Accept",
                     "choiceArgument": {"extraArgs": {
                         "context": ctx.get("choiceContextData", {}),
                         "meta": {"values": {}}}}}}],
                 act_as=receiver, disclosed=ctx.get("disclosedContracts", []))
        print(f"\n  PHASE 3  accepted by the receiver")

    after = balances(("sender", sender), ("receiver", receiver))
    show("\n  FINAL (read back from the ledger)", after)

    moved = after["receiver"]["total"] - before["receiver"]["total"]
    paid = before["sender"]["total"] - after["sender"]["total"]
    ok = moved == float(AMOUNT) and paid == float(AMOUNT) and after["sender"]["locked"] == 0
    print(f"\n  receiver gained {moved}, sender paid {paid}, no funds left locked: "
          f"{after['sender']['locked'] == 0}")
    print("  RESULT:", "real token-standard transfer settled ✓" if ok
          else "MISMATCH -- see the numbers above")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
