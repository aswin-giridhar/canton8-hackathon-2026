"""Prove the 900s expiry against real DevNet, not a fake clock.

Holds ONE token (the c8lab.py behaviour: cache and never refresh) and polls the
ledger until DevNet rejects it. Then refreshes and shows the call recover.

This is the difference between "expires_in says 900" and "we watched it die".
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request

IDP  = os.environ["C8_IDP"]; CID = os.environ["C8_CLIENT_ID"]
SEC  = os.environ["C8_CLIENT_SECRET"]; BASE = os.environ["C8_BASE"]


def mint():
    d = urllib.parse.urlencode({"grant_type": "client_credentials",
                                "client_id": CID, "client_secret": SEC}).encode()
    r = json.loads(urllib.request.urlopen(urllib.request.Request(
        f"{IDP}/realms/master/protocol/openid-connect/token", data=d), timeout=30).read())
    return r["access_token"], r["expires_in"]


def call(tok):
    try:
        req = urllib.request.Request(f"{BASE}/v2/state/ledger-end",
                                     headers={"Authorization": f"Bearer {tok}"})
        urllib.request.urlopen(req, timeout=30).read()
        return 200
    except urllib.error.HTTPError as e:
        return e.code


tok, ttl = mint()
t0 = time.time()
print(f"minted a token, expires_in={ttl}s. polling until DevNet rejects it.", flush=True)
last = 200
while time.time() - t0 < 1500:
    code = call(tok)
    el = int(time.time() - t0)
    if code != last:
        print(f"  t+{el:4d}s  status changed {last} -> {code}", flush=True)
        last = code
    if code == 401:
        print(f"\nTOKEN DIED at t+{el}s (expires_in claimed {ttl}s).", flush=True)
        print("A cache-forever client returns 401 from here on.", flush=True)
        tok2, _ = mint()
        print(f"after refresh: HTTP {call(tok2)}  <- recovered", flush=True)
        sys.exit(0)
    time.sleep(30)
print("token still alive after 1500s - expiry NOT reproduced", flush=True)
sys.exit(1)
