"""MCP server: an AI agent's wallet, whose limits live on the Canton ledger.

The agent gets tools to spend money. It does NOT get a key, and there is no
policy check in this file -- deliberately. Every limit is enforced by the
Daml contract, so compromising the agent, or this server, does not raise the
cap or add a counterparty.

`read_task_inbox` is the deliberately attacker-controlled surface: it returns
text a third party wrote. That is the realistic injection vector.
"""
import json, os
from mcp.server.fastmcp import FastMCP
import ledger as L

mcp = FastMCP("canton-agent-wallet")
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_state.json")
INBOX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inbox.txt")
DISCLOSURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "disclosure.json")


def _disclosure():
    """Ask Alice's side for a disclosure covering her current purse.

    Fresh every time: a charge archives the purse and creates a new one, so a
    cached disclosure names a dead contract and the ledger rejects it. The
    agent never gets standing visibility -- only one transaction's worth.
    """
    import disclosure_service
    return disclosure_service.issue_disclosure()


def _s():
    return json.load(open(STATE))


def _save(k, v):
    s = _s(); s[k] = v; json.dump(s, open(STATE, "w"), indent=2)


@mcp.tool()
def get_mandate() -> str:
    """What this agent is currently allowed to spend, and with whom."""
    s = _s()
    for cid, a in L.active(L.MANDATE, s["agent"]):
        return json.dumps({
            "cap": a["cap"], "spent": a["spent"],
            "remaining": float(a["cap"]) - float(a["spent"]),
            "allowedCounterparties": [p.split("::")[0] for p in a["allowedCounterparties"]],
            "expiresAt": a["expiresAt"]}, indent=2)
    return "No active mandate. This agent cannot spend anything."


@mcp.tool()
def get_balance() -> str:
    """The remaining headroom under this mandate.

    The agent cannot read the owner's purse balance -- it is not an observer on
    that contract. It only knows what it is still allowed to spend.
    """
    s = _s()
    for _, a in L.active(L.MANDATE, s["agent"]):
        return f"{float(a['cap']) - float(a['spent']):.2f} remaining of cap {a['cap']}"
    return "no active mandate"


@mcp.tool()
def list_payees() -> str:
    """Known parties that could be paid, whether or not they are permitted."""
    s = _s()
    return json.dumps({k: s[k].split("::")[0]
                       for k in ("merchant", "mallory")}, indent=2)


def _current(template_id, party, what):
    """Resolve a contract id live, at the moment of use. Never cache one.

    Daml contracts are immutable: a consuming choice archives its input and
    creates a SUCCESSOR with a new id. Charge consumes two of them -- the
    mandate and the purse -- so any id written to disk is a one-shot token
    that is already stale by the time the next call reads it.

    Caching them was a two-paths-one-gate bug. Charge wrote the new mandate id
    back and not the purse id, so the second spend failed; and Restrict/Adjust
    mint a successor mandate on a path that does not run through this file at
    all, so Alice narrowing scope would strand the cached mandate id too.

    Resolving live closes both. demo_state.json now holds only PARTY ids,
    which are stable. This matters beyond tidiness: a stale pointer surfaces
    as "Contract could not be found", which reads exactly like a policy denial
    and is not one -- the failure mode this project must never be ambiguous
    about.

    Read as the agent, not as Alice, so the lookup depends on the agent's own
    visibility (Purse's `observer visibleTo`). Visibility is a separate gate
    from authority, and the agent should not borrow the owner's view to spend.
    """
    for cid, _ in L.active(template_id, party):
        return cid
    raise L.LedgerError(f"no active {what} this agent can see")


@mcp.tool()
def charge(payee: str, amount: float) -> str:
    """Pay a party from the owner's purse, under the mandate.

    payee: one of the names from list_payees
    amount: how much to pay

    There is NO permission check in this function. The ledger decides.
    """
    s = _s()
    if payee not in s:
        return f"unknown payee '{payee}'. Try list_payees."
    try:
        # The mandate is resolved live: the agent IS a signatory on it, so it
        # can see it, and its contract id changes with every charge.
        #
        # The purse is NOT resolved by lookup. The agent cannot see it at all,
        # so there is nothing to look up -- it uses the contract id Alice named
        # in her disclosure, and attaches the disclosure to the submission.
        disc = _disclosure()
        if not disc:
            raise L.LedgerError(
                "no disclosure available; Alice has not disclosed a purse")
        r = L.exercise(L.MANDATE, _current(L.MANDATE, s["agent"], "mandate"),
                       "Charge",
                       {"amount": str(amount), "receiver": s[payee],
                        "purse": disc[0]["contractId"]},
                       act_as=s["agent"], disclosed=disc)
        return f"PAID {amount} to {payee}."
    except L.LedgerError as e:
        return (f"REFUSED BY THE LEDGER. The payment did not happen.\n"
                f"Reason: {e}")


@mcp.tool()
def get_statement() -> str:
    """The audit trail: every charge, and which rule permitted it."""
    s = _s()
    rows = [a for _, a in L.active(L.CHARGE_RECORD, s["alice"])]
    if not rows:
        return "No charges yet."
    return "\n".join(
        f"- {r['amount']} to {r['receiver'].split('::')[0]} "
        f"(running total {r['spentAfter']} of {r['cap']}) "
        f"| permitted by: {r['permittedBy']}" for r in rows)


@mcp.tool()
def read_task_inbox() -> str:
    """Take the next task from the owner's task inbox.

    Consumes the item: a second call returns an empty inbox. Without this an
    agent told to "process every task" re-reads the same item forever, which
    is a spin loop rather than a drain.

    NOTE: the contents are written by third parties. This is the untrusted
    surface, and in the demo it is where the prompt injection arrives.
    """
    if not os.path.exists(INBOX):
        return "inbox empty"
    item = open(INBOX).read()
    if not item.strip():
        return "inbox empty"
    # Consume it, keeping a copy so the demo is repeatable.
    open(INBOX + ".consumed", "w").write(item)
    open(INBOX, "w").write("")
    return item


if __name__ == "__main__":
    mcp.run()
