"""The mandate moves REAL Canton Coin.

Joins the two halves of the project. Until now the Mandate debited our own
`Purse` template, and the token-standard transfer was a separate script. Here
`ChargeViaTokenStandard` executes a real `TransferFactory_Transfer` on Amulet,
with the ledger enforcing the cap and allow-list on the transfer that actually
runs.

The agent submits ALONE. It holds no key and the owner does not sign at spend
time -- the Mandate carries the owner's authority because the owner is a
signatory on it.

Run LocalNet, upload the DAR, then from hackathon-toolkit/:
    python3 ../token-standard/mandate_moves_amulet.py
"""
import datetime, json, sys
sys.path.insert(0, ".")
import c8lab as C

PKG = "#agent-mandate"
MANDATE = f"{PKG}:Mandate:Mandate"
PROPOSAL = f"{PKG}:Mandate:MandateProposal"
RECORD = f"{PKG}:Mandate:ChargeRecord"
AMOUNT = "12.0"
CAP = "50.0"


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def pending_instructions(party):
    """All pending offers. TransferInstruction is an INTERFACE, not a template
    -- a TemplateFilter returns NO_TEMPLATES_FOR_PACKAGE_NAME, and the nested
    tree from submit-and-wait does not surface it either.

    Returns a SET so callers can diff. Taking "the first pending offer" once
    accepted a leftover from an earlier run and reported success: the net
    numbers looked right and the causality was wrong.
    """
    body = {"filter": {"filtersByParty": {party: {"cumulative": [
                {"identifierFilter": {"InterfaceFilter": {"value": {
                    "interfaceId": C.TRANSFER_INSTRUCTION,
                    "includeInterfaceView": True,
                    "includeCreatedEventBlob": False}}}}]}}},
            "verbose": False, "activeAtOffset": C.ledger_end()}
    out = set()
    for item in C.call("/v2/state/active-contracts", body):
        ev = item.get("contractEntry", {}).get("JsActiveContract", {}).get("createdEvent", {})
        if ev:
            out.add(ev["contractId"])
    return out


def live_mandates(party):
    return {cid: a for cid, a in _active(MANDATE, party)}


def holding_disclosures(party):
    """Disclose the owner's Amulet holdings for ONE transaction.

    The agent is not a stakeholder on the owner's coin and cannot see it --
    submitting without this fails with CONTRACT_NOT_FOUND on the input holding,
    which reads like a stale contract and is actually the privacy model. Each
    charge carries a fresh disclosure; the agent never gets standing sight of
    the owner's funds.
    """
    body = {"filter": {"filtersByParty": {party: {"cumulative": [
                {"identifierFilter": {"InterfaceFilter": {"value": {
                    "interfaceId": C.HOLDING,
                    "includeInterfaceView": True,
                    "includeCreatedEventBlob": True}}}}]}}},
            "verbose": False, "activeAtOffset": C.ledger_end()}
    out = []
    for item in C.call("/v2/state/active-contracts", body):
        ac = item.get("contractEntry", {}).get("JsActiveContract", {})
        ev = ac.get("createdEvent", {})
        if ev.get("createdEventBlob"):
            out.append({"templateId": ev["templateId"],
                        "contractId": ev["contractId"],
                        "createdEventBlob": ev["createdEventBlob"],
                        "synchronizerId": ac.get("synchronizerId", "")})
    return out


def amulet(p):
    return sum(float(h["amount"]) for h in C.holdings(p) if not h["locked"])


def main():
    owner = C.find_party("app_user")                 # holds the Canton Coin
    agent = C.allocate_party("amulet_agent")          # the AI agent
    receiver = C.find_party("mandate_receiver")       # allow-listed counterparty
    dso = C.dso_party()

    print(f"  owner    {owner.split('::')[0]}  ({amulet(owner):.2f} Amulet)")
    print(f"  agent    {agent.split('::')[0]}  (holds no coin, holds no key)")
    print(f"  receiver {receiver.split('::')[0]}  ({amulet(receiver):.2f} Amulet)")

    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

    # --- the owner grants a mandate -------------------------------------
    prop = C.submit([{"CreateCommand": {"templateId": PROPOSAL, "createArguments": {
        "owner": owner, "spender": agent, "cap": CAP,
        "allowedCounterparties": [receiver],
        "expiresAt": iso(now + datetime.timedelta(hours=24))}}}],
        act_as=owner, want_transaction=True)
    pcid = C._find_instruction_cid(prop) or _first(prop, "MandateProposal")
    acc = C.submit([{"ExerciseCommand": {"templateId": PROPOSAL, "contractId": pcid,
                                         "choice": "Accept", "choiceArgument": {}}}],
                   act_as=agent, want_transaction=True)
    mandate = _first(acc, "Mandate:Mandate")
    print(f"\n  mandate  cap {CAP}, allow-list [receiver], spender=agent")

    # --- phase 1: the registry hands over the issuer's config ------------
    holdings = [h for h in C.holdings(owner)
                if not h["locked"] and h["instrument"] == "Amulet"]
    args = {"expectedAdmin": dso,
            "transfer": {"sender": owner, "receiver": receiver, "amount": AMOUNT,
                         "instrumentId": {"admin": dso, "id": "Amulet"},
                         "requestedAt": iso(now),
                         "executeBefore": iso(now + datetime.timedelta(hours=24)),
                         "inputHoldingCids": [h["contractId"] for h in holdings],
                         "meta": {"values": {}}},
            "extraArgs": {"context": {"values": {}}, "meta": {"values": {}}}}
    fac = C.registry("/registry/transfer-instruction/v1/transfer-factory",
                     {"choiceArguments": args})
    cc = fac.get("choiceContext", {})
    args["extraArgs"]["context"] = cc.get("choiceContextData", {})
    hd = holding_disclosures(owner)
    print(f"  registry transferKind={fac.get('transferKind')}, "
          f"{len(cc.get('disclosedContracts', []))} issuer-config disclosures")
    print(f"  owner discloses {len(hd)} holding(s) for this one transaction "
          f"(the agent cannot otherwise see them)")

    before = (amulet(owner), amulet(receiver))
    # Successors accumulate across runs, so snapshot and diff rather than
    # counting -- the same trap the W3 harness hit.
    mandates_before = set(live_mandates(agent))
    offers_before = pending_instructions(owner)

    # --- phase 2: the AGENT submits, alone ------------------------------
    res = C.submit([{"ExerciseCommand": {
                       "templateId": MANDATE, "contractId": mandate,
                       "choice": "ChargeViaTokenStandard",
                       "choiceArgument": {"factoryCid": fac["factoryId"],
                                          "transferArgs": args}}}],
                   act_as=agent,
                   disclosed=(cc.get("disclosedContracts", [])
                              + holding_disclosures(owner)),
                   want_transaction=True)
    new_offers = pending_instructions(owner) - offers_before
    if len(new_offers) > 1:
        raise SystemExit(f"expected at most one new offer, saw {len(new_offers)}")
    instruction = next(iter(new_offers), None)
    print(f"  agent exercised ChargeViaTokenStandard ALONE -> "
          f"offer {(instruction or '(direct)')[:24]}...")

    # --- phase 3: an offer still needs accepting ------------------------
    if instruction:
        ctx = C.registry(f"/registry/transfer-instruction/v1/{instruction}"
                         "/choice-contexts/accept", {"meta": {}})
        C.submit([{"ExerciseCommand": {
                     "templateId": C.TRANSFER_INSTRUCTION, "contractId": instruction,
                     "choice": "TransferInstruction_Accept",
                     "choiceArgument": {"extraArgs": {
                         "context": ctx.get("choiceContextData", {}),
                         "meta": {"values": {}}}}}}],
                 act_as=receiver, disclosed=ctx.get("disclosedContracts", []))
        print("  receiver accepted")

    after = (amulet(owner), amulet(receiver))
    print(f"\n  owner    {before[0]:.2f} -> {after[0]:.2f}")
    print(f"  receiver {before[1]:.2f} -> {after[1]:.2f}")

    # --- the mandate's own state, read back -----------------------------
    after_m = live_mandates(agent)
    successors = [a for cid, a in after_m.items() if cid not in mandates_before]
    spent = successors[0]["spent"] if len(successors) == 1 else None
    recs = [a for _, a in _active(RECORD, owner)]
    print(f"  mandate spent = {spent} of {CAP}")
    if recs:
        print(f"  audit: {recs[-1]['amount']} to receiver | {recs[-1]['permittedBy']}")

    moved = after[1] - before[1]
    ok = moved == float(AMOUNT) and spent and float(spent) == float(AMOUNT)
    print("\n  RESULT:", "the mandate moved REAL Canton Coin ✓" if ok
          else f"MISMATCH: moved {moved}, spent {spent}")
    return 0 if ok else 1


def _first(res, frag):
    for ev in res.get("transaction", {}).get("events", []):
        c = ev.get("CreatedTreeEvent", {}).get("value") or ev.get("CreatedEvent")
        if c and frag in str(c.get("templateId", "")):
            return c["contractId"]
    return None


def _active(tid, party):
    body = {"filter": {"filtersByParty": {party: {"cumulative": [
                {"identifierFilter": {"TemplateFilter": {"value": {
                    "templateId": tid, "includeCreatedEventBlob": False}}}}]}}},
            "verbose": False, "activeAtOffset": C.ledger_end()}
    out = []
    for item in C.call("/v2/state/active-contracts", body):
        ev = item.get("contractEntry", {}).get("JsActiveContract", {}).get("createdEvent", {})
        if ev:
            out.append((ev["contractId"], ev.get("createArgument", {})))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
