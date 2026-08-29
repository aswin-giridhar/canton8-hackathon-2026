"""Expiry logic, tested with a fake clock instead of waiting 15 minutes."""
import auth

def test():
    clock = {"t": 1000.0}
    issued = []
    def fake_fetch():
        issued.append(clock["t"])
        return f"token-{len(issued)}", 900.0     # the real DevNet TTL

    src = auth.TokenSource("idp", "id", "sec",
                           now_fn=lambda: clock["t"], fetch_fn=fake_fetch)

    assert src.token() == "token-1", "first call must mint"
    clock["t"] += 100
    assert src.token() == "token-1", "must reuse a live token"
    assert src.refreshes == 1

    # 840s in: inside the 60s skew window, so it must refresh EARLY --
    # before the server would reject it.
    clock["t"] = 1000 + 841
    assert src.token() == "token-2", "must refresh before expiry, not after"
    assert src.refreshes == 2

    # A 401 beats our arithmetic: the server is the authority.
    src.invalidate()
    assert src.token() == "token-3"
    assert src.refreshes == 3

    # The bug this exists to prevent: c8lab.py caches forever, so at 15 min
    # and beyond it would still be handing out token-1.
    clock["t"] = 1000 + 5000
    assert src.token() == "token-4", "a long-running process must keep working"
    print(f"PASS: {src.refreshes} refreshes over ~83 min of simulated runtime;")
    print("      a never-refreshing cache would have died at minute 15.")

if __name__ == "__main__":
    test()
