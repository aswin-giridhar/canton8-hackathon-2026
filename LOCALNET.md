# LocalNet on this machine — it runs in 8 GB

`SETUP.md` says Docker needs **16 GB** and that the compose file "wants about
12 GB, so 8 GB thrashes". Measured here, that is conservative: with the
`resource-constraints.yaml` overlay that the documented command already
includes, the whole stack runs inside an **8 GB** WSL2 VM.

**I told the user this would not fit, and I was wrong twice.** First I reported
WSL's 8 GB slice as though it were the machine's RAM (the host has 31.8 GB).
Then, having corrected that, I still judged 8 GB too small. It runs.

## Measured footprint

```
canton     3.04 GiB / 4 GiB    76%
splice     1.35 GiB / 3 GiB    45%
postgres   1.03 GiB / 2 GiB    52%
nginx      6.3 MiB  / 32 MiB   20%
6 web UIs  ~13 MiB each
                              ---- ~5.4 GiB of container memory
```

Host-side it is genuinely tight — 399 MiB free in the VM — but nothing OOMs and
every container reports healthy.

## Start it

Images (~4 GB on disk) and the bundle are already pulled/extracted here.

```bash
cd ~/localnet/splice-node/docker-compose/localnet
export LOCALNET_DIR=$PWD
export IMAGE_TAG=0.6.8
export PARTY_HINT=agentmandate-dev-1        # must be word-word-number
export APP_PROVIDER_UI_PORT=3001            # 3000 is usually taken

docker compose --env-file "$LOCALNET_DIR/compose.env" \
  --env-file "$LOCALNET_DIR/env/common.env" \
  -f "$LOCALNET_DIR/compose.yaml" \
  -f "$LOCALNET_DIR/resource-constraints.yaml" \
  --profile sv --profile app-provider --profile app-user up -d
```

Same command with `down -v` to stop and wipe. Takes ~5 minutes to reach healthy.

**The bundle version must match the image tag.** The official docs link to
v0.7.5; `SETUP.md` pins images at 0.6.8. Use the matching bundle:

```bash
gh release download v0.6.8 -R digital-asset/decentralized-canton-sync \
   -p "0.6.8_splice-node.tar.gz" -D ~/localnet
tar xzf ~/localnet/0.6.8_splice-node.tar.gz -C ~/localnet
```

## Verified working

```
:2975 / :3975 / :4975  ledger-end -> HTTP 401     (401 = up, wants a token)
scan registry           /registry/metadata/v1/info -> 200
                        DSO::1220115f5c4661632cb5335579ba97463549e6d615190288fd79a2b3ff831f258424

python3 c8lab.py check
  token ok · ledger end 33 · 2 local parties
```

The registry is Host-routed: `curl -H "Host: scan.localhost" http://localhost:4000/...`.

## Why this matters

LocalNet **mints Canton Coin on its own** as mining rounds pay the validator,
whereas on DevNet a fresh party holds nothing and funding must be requested from
the Cantor8 team. That is the blocker this removes: the real token-standard
transfer needs funded holdings, and here they arrive without asking anyone.

## Note on `.wslconfig` — no change required

`~/.wslconfig` is unchanged at `memory=8GB`, which is all
LocalNet needs.

It was briefly raised to 18GB in anticipation of needing more, then **reverted
and verified byte-identical to the original**. The raise never took effect
anyway — that requires `wsl --shutdown`, which never ran.

One thing worth recording: the cap applies to **every** WSL2 VM, including
Docker Desktop's engine VM, which is where the containers actually run. So
running `docker` from Windows PowerShell rather than from WSL would not have
changed the memory available to them — it is the same VM either way.
