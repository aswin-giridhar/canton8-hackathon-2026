"""Set up the demo world on the sandbox, and print what it made.

Alice funds a purse and mandates an AI agent to spend up to 100 with the
merchant only. Mallory is the attacker: a real party, deliberately not on
the allow-list.
"""
import datetime, json, sys
import ledger as L

STATE = "demo_state.json"


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    alice    = L.allocate_party("alice")
    agent    = L.allocate_party("agent")
    merchant = L.allocate_party("merchant")
    mallory  = L.allocate_party("mallory")

    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

    # Clear any purse from an earlier run so the demo is repeatable.
    for cid, _ in L.active(L.PURSE, alice):
        L.exercise(L.PURSE, cid, "Archive", {}, act_as=alice)

    # Alice's money. NOTE visibleTo = [] -- the agent is NOT an observer and
    # cannot see this contract at all. It gets access per-transaction, via an
    # explicit disclosure Alice hands out, exactly as the token standard's
    # registry does. A permanent observer would leak every future holding too.
    purse_r = L.create(L.PURSE,
                       {"owner": alice, "amount": "500.0", "visibleTo": []},
                       act_as=alice)
    purse = L.first_created(purse_r, "Purse")

    # Sanity-check that Alice can disclose the purse. The MCP server does not
    # read a file for this -- it calls disclosure_service.issue_disclosure()
    # fresh per charge, because a charge archives the purse and a cached
    # disclosure would name a dead contract.
    disclosure = L.disclosure_for(L.PURSE, alice)

    prop_r = L.create(L.MANDATE_PROPOSAL,
                      {"owner": alice, "spender": agent, "cap": "100.0",
                       "allowedCounterparties": [merchant],
                       "expiresAt": iso(now + datetime.timedelta(hours=24))},
                      act_as=alice)
    prop = L.first_created(prop_r, "MandateProposal")

    acc_r = L.exercise(L.MANDATE_PROPOSAL, prop, "Accept", {}, act_as=agent)
    mandate = L.first_created(acc_r, "Mandate:Mandate") or L.first_created(acc_r, "Mandate")

    state = {"alice": alice, "agent": agent, "merchant": merchant,
             "mallory": mallory, "purse": purse, "mandate": mandate}
    json.dump(state, open(STATE, "w"), indent=2)

    print("demo world ready\n")
    for k in ("alice", "agent", "merchant", "mallory"):
        print(f"  {k:9} {state[k][:52]}...")
    print(f"\n  purse    500.0, owned by alice, visibleTo=[] "
          f"(agent is NOT an observer)")
    print(f"  disclosure available: {len(disclosure)} contract(s) "
          f"(issued fresh per charge, never cached)")
    print(f"  mandate  cap 100.0, allow-list [merchant], expires in 24h")
    print(f"\n  mallory is a real party and is NOT on the allow-list.")
    return state


if __name__ == "__main__":
    try:
        main()
    except L.LedgerError as e:
        print(f"\nLEDGER ERROR: {e}", file=sys.stderr); sys.exit(1)
