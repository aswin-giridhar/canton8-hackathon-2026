# Message to send Davide (copy-paste)

Short version, leads with the thing that's cheapest for him to do.

---

Hi Davide — two things, one ask and one finding.

**The ask:** could you send some test tokens (`c8TEST` ideally, or Canton Coin)
to this party on DevNet?

```
agentmandate-aswin-1::12204e94c0e449c0efcd270dd1e68259c36471cebef132e5c7dfc2750fe8c9eed77f
```

We've got the full token-standard flow working end to end — auth, party
allocation, act-as grant, the registry `transfer-factory` call (returns
`transferKind: offer` with 2 disclosed contracts and a `tokenConfigCid`), and the
`TransferFactory_Transfer` submission with those attached. It reaches the ledger
and stops on the issuer's own `AssertionFailed: 'Insufficient funds'`. Funding is
the only missing piece.

**The finding, which might be worth a line in the toolkit:** the DevNet Keycloak
token has `expires_in: 900`, and `c8lab.py`'s `token()` caches it in `_tok` and
never refreshes. Anything long-running — an A1 indexer especially, since that
task *requires* a continuous stream — starts fine and then 401s at minute 15. It
reads like a streaming bug and it's an auth bug. Probably worth warning the API
track about.

Three smaller ones while I'm here:

- `dso_party()` fails on DevNet. `/v2/parties` is paginated (10k cap,
  `nextPageToken`) and `parties()` only reads page one, so the DSO sorts outside
  it. Setting `C8_ADMIN_PARTY` fixes it. The DSO id is available with no auth
  from `sv-proxy.../registry/metadata/v1/info`.
- `c8lab.py check` loops all 5,784 local parties with one ACS call each — ≥13
  minutes on DevNet, so "run check first" doesn't hold there.
- **Good news:** party allocation on DevNet does *not* need the external-party
  topology flow that the README warns about. Plain `POST /v2/parties` returns 200
  with `isLocal: true`. Happy to send a PR if useful.

Full write-up in `devnet-findings.md` if you want the detail.

Thanks!
