"""Expiry and concurrent refresh, without waiting 15 real minutes."""
import concurrent.futures
import threading
import time
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

    # W3 uses concurrent submitters. They must share one refresh rather than
    # stampeding the IDP when all workers see the same expired token.
    gate = threading.Barrier(8)
    concurrent_fetches = []
    def slow_fetch():
        concurrent_fetches.append(clock["t"])
        time.sleep(0.02)
        return "shared-token", 900.0
    concurrent_src = auth.TokenSource(
        "idp", "id", "sec", now_fn=lambda: clock["t"], fetch_fn=slow_fetch)
    def worker():
        gate.wait()
        return concurrent_src.token()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        tokens = list(pool.map(lambda _: worker(), range(8)))
    assert tokens == ["shared-token"] * 8
    assert concurrent_src.refreshes == 1
    assert len(concurrent_fetches) == 1, "concurrent refresh must mint once"

    print(f"PASS: {src.refreshes} refreshes over ~83 min of simulated runtime;")
    print("      a never-refreshing cache would have died at minute 15.")
    print("PASS: 8 concurrent callers shared exactly 1 token refresh.")

if __name__ == "__main__":
    test()
