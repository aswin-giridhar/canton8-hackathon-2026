"""Thin JSON Ledger API v2 client for the local Canton sandbox.

Stdlib only, same reason the toolkit's c8lab.py is: no pip on the day.

This talks to a REAL Canton ledger (daml sandbox), not a mock. That matters:
the whole claim of this project is that the mandate's limits are enforced by
the ledger, so a demo against a fake ledger would prove nothing.
"""
import json, urllib.error, urllib.request, uuid, os

BASE = os.environ.get("WALLET_LEDGER", "http://localhost:7575")
USER = os.environ.get("WALLET_USER", "participant_admin")

# Full package id, not "#agent-mandate". The package-name reference needs an
# UPGRADABLE package, and ours depends on daml-script (the compiler warns about
# this), which disqualifies it. Splitting tests into their own package is the
# proper fix; see RESULTS.md. The package id works today and is unambiguous.
PKG = "2da421f913f3848c625394c29e08bca6d39ee2d2671406e4ff65eda1dc388160"
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


def submit(commands, act_as, read_as=None):
    return _req("/v2/commands/submit-and-wait-for-transaction",
                {"commands": {"commands": commands,
                              "commandId": f"wallet-{uuid.uuid4()}",
                              "actAs": act_as if isinstance(act_as, list) else [act_as],
                              "readAs": read_as or [],
                              "userId": USER}})


def create(template_id, args, act_as):
    return submit([{"CreateCommand": {"templateId": template_id,
                                      "createArguments": args}}], act_as)


def exercise(template_id, contract_id, choice, arg, act_as, read_as=None):
    return submit([{"ExerciseCommand": {"templateId": template_id,
                                        "contractId": contract_id,
                                        "choice": choice,
                                        "choiceArgument": arg}}], act_as, read_as)


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
