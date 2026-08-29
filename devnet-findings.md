# Cantor8 DevNet: what actually works, measured

Measured 29 Aug 2026 against `api.validator.dev.digik.cantor8.tech` with the
`hackathon` Keycloak client. Every number below came from a command in this
file. Nothing here is inferred from the docs.

The toolkit's README says party allocation is the unverified DevNet step. That
turned out not to be the thing that breaks first.

## Working config

```bash
export C8_BASE=https://api.validator.dev.digik.cantor8.tech/api/ledger
export C8_IDP=https://auth.dev.digik.cantor8.tech
export C8_CLIENT_ID=hackathon
export C8_CLIENT_SECRET=<the secret>
export C8_REGISTRY=https://sv-proxy.dev.digik.cantor8.tech
export C8_ADMIN_PARTY=DSO::1220be58c29e65de40bf273be1dc2b266d43a9a002ea5b18955aeef7aac881bb471a
```

The last two are **not optional on DevNet**, and the README does not say so.
`C8_ADMIN_PARTY` is the workaround for finding #2.

Confirmed working: token issuance (HTTP 200), `GET /v2/state/ledger-end`
(offset 2,918,048), `GET /v2/parties` (HTTP 200), `POST /v2/state/active-contracts`
via `holdings()` (HTTP 200).

---

## 1. The token expires in 15 minutes and `c8lab.py` never refreshes it

**The one that will cost someone their afternoon.**

```bash
curl -s -X POST https://auth.dev.digik.cantor8.tech/realms/master/protocol/openid-connect/token \
  -d grant_type=client_credentials -d client_id=hackathon -d client_secret=$C8_CLIENT_SECRET
```

```
expires_in: 900          # 15 minutes
sub:        validator-backend@clients
aud:        [https://ledger_api.validator.dev.digik.cantor8.tech,
             https://validator.dev.digik.cantor8.tech/api]
scope:      validator-api-audience ledger-api-audience
```

`c8lab.py:token()` caches into `_tok["t"]` on first call and returns it forever.
There is no expiry check and no refresh.

Why it matters more than the rest: **challenge A1 asks for a service that streams
updates continuously and survives a restart.** That process starts working, then
returns 401 at minute 15. It reads like a streaming bug and it is an auth bug.
Anyone building A1, A2, or any daemon needs to re-mint on expiry (or just
re-mint every call — it took 0.4s warm).

Note also that `sub` is `validator-backend@clients` regardless of what you pass.
On the `IDP` path `token(sub)` ignores its argument entirely, so `sub=ADMIN` and
`sub=USER` are the same identity — while `submit()` still writes `userId: sub`
into the request body. LocalNet and DevNet differ here despite the README's
"everything else is the same".

## 2. `dso_party()` fails on DevNet, which breaks lab steps 3 and 6

```
c8lab.dso_party()
  -> LabError: could not find the DSO party. On LocalNet it appears once
     the network has bootstrapped; wait and retry.
```

The advice is wrong here — waiting does not help. The DSO exists:

```bash
curl -s https://sv-proxy.dev.digik.cantor8.tech/registry/metadata/v1/info
{"adminId":"DSO::1220be58c29e65de40bf273be1dc2b266d43a9a002ea5b18955aeef7aac881bb471a", ...}
```

**No auth needed for that call.** The cause is finding #3.

This breaks `create_preapproval_proposal()` (step 3) and `transfer()` (step 6),
since both call `dso_party()`. Setting `C8_ADMIN_PARTY` to the value above fixes
it and returns instantly — verified.

## 3. `/v2/parties` is paginated and `parties()` reads only the first page

```bash
curl -s -H "Authorization: Bearer $TOK" "$C8_BASE/v2/parties?pageSize=5"
# -> 5 partyDetails + "nextPageToken": "Clsw..."
```

Unpaged, the endpoint returns exactly 10,000 parties (5,784 `isLocal`) and a
`nextPageToken`. `c8lab.py:parties()` never reads that token, so it sees one
page and believes that is the whole network. The DSO sorts outside it.

Any code doing party discovery on DevNet has to follow `nextPageToken`.

## 4. `python3 c8lab.py check` does not finish in useful time

`check()` prints all 5,784 local parties, then runs one ACS query per party.

```
token()          30.11s   (cold; ~0.4s warm)
local_parties()  16.13s   -> 5784 parties   (639 KB response)
holdings() x1     0.13s   -> 0 holdings
```

**At least ~13 minutes** of sequential ACS calls, extrapolated from a single
call that returned an *empty* ACS. A party holding contracts returns a larger
payload and will be slower, so treat 13 min as a floor, not an estimate.

The doc says "`check` first, always." On DevNet that advice does not hold.
Check a single named party instead.

## 5. This credential is not accepted by the scanner API

```bash
curl -H "Authorization: Bearer $TOK" \
  https://scanner-ledger-read-api.dev.digik.cantor8.tech/tokens/owners?limit=5
# HTTP 401  "unauthorized"
```

API.md says scanner data endpoints need a token. The `hackathon` client token is
not that token — its `aud` covers the ledger API and validator API only. Whether
a different client/audience exists for the scanner is **unknown**; this is one
negative result, not proof. Worth asking Davide.

Health endpoints need no auth and do work:

```bash
curl -s https://scanner-ledger-read-api.dev.digik.cantor8.tech/health
{"status":"ok","db":{"status":"ok","scannerDelaySecs":0.798},
 "streams":{"scan/process/ledgerUpdatesMain":{"status":"stale","staleSecs":3618}, ...}}
```

Note several scanner streams reported **stale for ~1 hour** at time of testing,
while `scannerDelaySecs` read 0.8. Worth knowing if you plan to use the scanner
as a reference for A1 — the summary field and the stream fields disagree.

## Reachable with no credentials at all

Useful if someone's creds are not working yet:

| URL | Status |
|---|---|
| `sv-proxy.../registry/metadata/v1/info` | 200, gives the DSO party |
| `sv-proxy.../api/scan/v0/scans` | 200, lists every SV scan node |
| `scanner-ledger-read-api.../health` | 200, index lag + stream staleness |
| `wallet-backend.../healthz` | 200 |

## Not yet tested

- **Party allocation** (`POST /v2/parties`) — the step the README flags as
  unverified. Untested here because it writes permanent state to a shared network.
- `transfer()` end to end, and whether `transferKind` comes back `direct` or `offer`.
- Whether the `hackathon` client has act-as rights on any party it can submit for.

---

# UPDATE — DevNet verified end to end, 29 Aug ~16:10

The "Not yet tested" section above is now resolved. Everything below was run
against live DevNet with the `hackathon` client.

## Party allocation on DevNet WORKS — plain `POST /v2/parties`

The toolkit README says:

> *"Not yet verified on DevNet. Party allocation there may need the
> external-party topology flow rather than `POST /v2/parties`."*

It does not. Plain `POST /v2/parties` returns **HTTP 200** with
`isLocal: true`:

```bash
curl -X POST "$C8_BASE/v2/parties" -H "Authorization: Bearer $TOK" \
     -H 'Content-Type: application/json' -d '{"partyIdHint":"agentmandate-aswin-1"}'
# -> {"partyDetails":{"party":"agentmandate-aswin-1::12204e94c0e4…","isLocal":true,…}}
```

Note the namespace `12204e94c0e4…` is the **same as the Cantor8 admin party**
`cantor8-digik-1::12204e94c0e4…`, so allocated parties are hosted on the
Cantor8 participant.

`POST /v2/users/{userId}/rights` also returns 200 for both
`validator-backend@clients` and `participant_admin`.

## The token-standard two-phase flow works on DevNet

Against the Cantor8 registry (`/api/c8` prefix, admin `cantor8-digik-1::…`):

```
POST /api/c8/registry/transfer-instruction/v1/transfer-factory   HTTP 200
  factoryId       00429e1e682fbbd187f3094fd789fa6f2c6470d5d144…
  transferKind    offer            (no preapproval on a fresh party)
  disclosed       2 contracts
  choiceContext   {"tokenConfigCid": …}
```

Submitting `TransferFactory_Transfer` with those disclosed contracts attached
reaches the ledger and is rejected by the issuer's own Daml:

```
Interpretation error: ... AssertionFailed: The requirement 'Insufficient funds'
was not met.
```

**That is the flow working.** Auth, party, rights, registry, choice context,
disclosed contracts and submission are all verified end to end. The only missing
piece is funding.

## What is still blocked, and it needs a human

A fresh party holds nothing, and there is no public funding route — the
registry's spec endpoints (`/openapi.json`, `/docs`) return **403**.

**The ask:** send test tokens (`c8TEST` is ideal, or Canton Coin) to

```
agentmandate-aswin-1::12204e94c0e449c0efcd270dd1e68259c36471cebef132e5c7dfc2750fe8c9eed77f
```

## The 900s expiry, now watched rather than inferred

Earlier this was `expires_in: 900` from the token response. It has now been
observed against live DevNet: one token was held and the ledger polled every 30s
until it was rejected.

```
minted a token, expires_in=900s. polling until DevNet rejects it.
  t+ 911s  status changed 200 -> 401
TOKEN DIED at t+911s (expires_in claimed 900s).

dead token   -> HTTP401
fresh token  -> HTTP200
```

**911 seconds — 15 minutes and 11 seconds.** A client that caches its token and
never refreshes, which is exactly what `c8lab.py:token()` does on the `IDP` path,
returns 401 from that point on and never recovers.

This matters most for challenge **A1**, which requires a service that *"stream[s]
updates forward… so it stays current"*. That service works for fifteen minutes
and then dies, and the symptom looks like a streaming or WebSocket fault.

Reproduce with `agent-wallet/devnet_expiry_proof.py`. The refresh-aware client is
`agent-wallet/auth.py`, with its expiry logic unit-tested in `test_auth.py`.

## Still true from the original findings

The other four breakages listed above are unchanged.
