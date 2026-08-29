"""Proves the agent has NO standing access to Alice's purse.

Without the per-transaction disclosure the charge must fail on visibility.
With it, the same charge must succeed. If both succeeded, the agent would
have had access all along and the disclosure would be decoration.
"""
import json, sys
import ledger as L
import disclosure_service

s = json.load(open("demo_state.json"))
disclosure = disclosure_service.issue_disclosure()


def try_charge(disclosed, label):
    try:
        r = L.exercise(L.MANDATE, s["mandate"], "Charge",
                       {"amount": "5.0", "receiver": s["merchant"],
                        "purse": disclosure[0]["contractId"]},
                       act_as=s["agent"], disclosed=disclosed)
        new = L.first_created(r, "Mandate:Mandate")
        if new:
            s["mandate"] = new
            json.dump(s, open("demo_state.json", "w"), indent=2)
        print(f"  {label}: SUCCEEDED")
        return True
    except L.LedgerError as e:
        msg = str(e)
        why = "not visible" if "not visible" in msg else msg[:110]
        print(f"  {label}: REFUSED -> {why}")
        return False


print("Can the agent spend Alice's purse?\n")
without = try_charge(None, "without disclosure")
with_   = try_charge(disclosure, "with disclosure   ")

print()
if not without and with_:
    print("PASS: the agent has no standing access. Disclosure grants exactly")
    print("      one transaction's worth of visibility, and nothing more.")
    sys.exit(0)
print("FAIL: disclosure is not the thing granting access.")
sys.exit(1)
