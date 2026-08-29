"""Thin JSON Ledger API v2 client for the local Canton sandbox.

Stdlib only, same reason the toolkit's c8lab.py is: no pip on the day.

This talks to a REAL Canton ledger (daml sandbox), not a mock. That matters:
the whole claim of this project is that the mandate's limits are enforced by
the ledger, so a demo against a fake ledger would prove nothing.
"""
import json, urllib.error, urllib.request, uuid, os

BASE = os.environ.get("WALLET_LEDGER", "http://localhost:7575")
USER = os.environ.get("WALLET_USER", "participant_admin")

# Package NAME reference, now that the templates package no longer depends on
# daml-script. Name references need an upgradable package; they survive a
# rebuild, whereas a package id changes every time the code does.
PKG = "#agent-mandate"
MANDATE          = f"{PKG}:Mandate:Mandate"
MANDATE_PROPOSAL = f"{PKG}:Mandate:MandateProposal"
CHARGE_RECORD    = f"{PKG}:Mandate:ChargeRecord"
PURSE            = f"{PKG}:Value:Purse"


class LedgerError(Exception):
    """A ledger rejection, carrying the reason the ledger actually gave."""


def _req(path, body=None, method=None):
    req = urllib.request.Request(
        BASE + path,
        method=method or ("POST" if body is not None else "GET"),
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        # Surface the ledger's own words. The demo depends on showing them.
        raise LedgerError(_extract_reason(detail))
    except urllib.error.URLError as e:
        raise LedgerError(f"cannot reach the ledger at {BASE}: {e.reason}")


def _extract_reason(detail):
    """Pull the human-readable rejection out of a Canton error payload."""
    try:
        d = json.loads(detail)
        msg = d.get("cause") or d.get("error") or json.dumps(d)
    except json.JSONDecodeError:
        msg = detail
    # Canton wraps assertion failures; the interesting part is after the colon.
    for marker in ("UNHANDLED_EXCEPTION", "Interpretation error"):
        if marker in msg:
            break
    return msg[:500]


def ledger_end():
    return _req("/v2/state/ledger-end")["offset"]


def allocate_party(hint):
    for p in _req("/v2/parties").get("partyDetails", []):
        if p["party"].split("::")[0] == hint:
            return p["party"]
    return _req("/v2/parties", {"partyIdHint": hint})["partyDetails"]["party"]


def submit(commands, act_as, read_as=None, disclosed=None):
    body = {"commands": commands,
            "commandId": f"wallet-{uuid.uuid4()}",
            "actAs": act_as if isinstance(act_as, list) else [act_as],
            "readAs": read_as or [],
            "userId": USER}
    if disclosed:
        body["disclosedContracts"] = disclosed
    return _req("/v2/commands/submit-and-wait-for-transaction",
                {"commands": body})


def create(template_id, args, act_as):
    return submit([{"CreateCommand": {"templateId": template_id,
                                      "createArguments": args}}], act_as)


def exercise(template_id, contract_id, choice, arg, act_as, read_as=None,
             disclosed=None):
    return submit([{"ExerciseCommand": {"templateId": template_id,
                                        "contractId": contract_id,
                                        "choice": choice,
                                        "choiceArgument": arg}}],
                  act_as, read_as, disclosed)


def disclosure_for(template_id, party):
    """Build explicit-disclosure payloads for contracts `party` can see.

    This is how Canton lets a submitter use a contract they are NOT a
    stakeholder on: someone who CAN see it hands over the created-event blob,
    good for that one transaction. It is the mechanism the token standard's
    registry uses, and it is strictly better than making the spender a
    permanent observer -- a permanent observer sees every future holding too.
    """
    body = {"filter": {"filtersByParty": {party: {"cumulative": [
                {"identifierFilter": {"TemplateFilter": {"value": {
                    "templateId": template_id,
                    "includeCreatedEventBlob": True}}}}]}}},
            "verbose": False, "activeAtOffset": ledger_end()}
    out = []
    for item in _req("/v2/state/active-contracts", body):
        ac = item.get("contractEntry", {}).get("JsActiveContract", {})
        ev = ac.get("createdEvent", {})
        if ev.get("createdEventBlob"):
            out.append({"templateId": ev["templateId"],
                        "contractId": ev["contractId"],
                        "createdEventBlob": ev["createdEventBlob"],
                        "synchronizerId": ac.get("synchronizerId", "")})
    return out


def active(template_id, party):
    """Active contracts of one template, visible to one party."""
    body = {"filter": {"filtersByParty": {party: {"cumulative": [
                {"identifierFilter": {"TemplateFilter": {"value": {
                    "templateId": template_id,
                    "includeCreatedEventBlob": False}}}}]}}},
            "verbose": False, "activeAtOffset": ledger_end()}
    out = []
    for item in _req("/v2/state/active-contracts", body):
        ev = (item.get("contractEntry", {})
                  .get("JsActiveContract", {}).get("createdEvent", {}))
        if ev:
            out.append((ev["contractId"], ev.get("createArgument", {})))
    return out


def first_created(result, name_fragment):
    """Dig a created contract id out of a transaction result."""
    for ev in result.get("transaction", {}).get("events", []):
        c = ev.get("CreatedTreeEvent", {}).get("value") or ev.get("CreatedEvent")
        if c and name_fragment in str(c.get("templateId", "")):
            return c["contractId"]
    return None
