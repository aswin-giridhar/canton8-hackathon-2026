"""Alice's side of the boundary: issues a fresh disclosure per transaction.

A disclosure names a specific contract id. Charge debits the purse, which
archives it and creates a new one, so a disclosure is good for exactly one
transaction -- re-using it gives "referring to inactive contracts". That is the
mechanism working, not a bug.

In production this is an HTTP endpoint on the owner's wallet, or the token
registry's `choice-contexts` endpoint, which is precisely what the Canton token
standard's registry does and why c8lab.py's transfer() is two-phase. Here it is
an in-process function against the same sandbox, and THAT IS THE MOCKED PART:
the trust boundary between agent and owner is not enforced by a process
boundary in this demo.

What is NOT mocked: the agent still cannot see the purse, and the ledger still
rejects any charge whose disclosure does not name a live contract.
"""
import json, os
import ledger as L

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_state.json")


def issue_disclosure():
    """Alice discloses her CURRENT purse, for one transaction."""
    alice = json.load(open(STATE))["alice"]
    disc = L.disclosure_for(L.PURSE, alice)
    if not disc:
        raise L.LedgerError("Alice has no purse to disclose")
    return disc
