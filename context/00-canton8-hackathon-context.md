# Cantor8 Canton Hackathon — working context

Compiled 29 Aug 2026. Everything marked **measured** was run against live DevNet
or the GitHub API in this session. Everything else is labelled inference.

---

## 1. The situation

| | |
|---|---|
| Toolkit repo | `github.com/Cantor8/hackathon-toolkit` (public, no licence, no issues/PRs) |
| Created | 27 Aug 2026 21:23 UTC — **two days before the event** |
| Last commit | `c5b1779`, 29 Aug 09:02 UTC, Davide Falcone |
| Local clone | up to date with `origin/main` (verified) |
| Our commits | none — this is **upstream reference material**, not our project |

The whole toolkit (1,517 lines) was written in ~36 hours by one person, and his
commits carry `Claude-Session:` trailers — it was itself written with Claude Code.

**Do not edit `hackathon-toolkit/`.** Our work goes in sibling directories.
Davide is the organiser and is "in the room all day" per CHALLENGES.md.

### Other teams (measured, via GitHub forks API)

Three forks exist, **all unmodified clones** — only the repo names were changed.
The name is the only signal of intent so far:

| Fork | Implied track |
|---|---|
| `sm-dev1409/Scandex` | A1, the scanner/indexer |
| `pkaysantana/canton-agent-mandate` | D1, the agent mandate wallet |
| `shuhanchang12/hackathon-toolkit` | unrenamed, unknown |

Nobody has pushed code yet.

**Measured at 12:40 on 29 Aug — this is a snapshot.** One fork's `pushed_at` was
already 11:30. Re-run `gh api repos/Cantor8/hackathon-toolkit/forks` before relying
on "nobody has started"; it will go stale within the hour.

### Sibling Cantor8 repos worth knowing

| Repo | Why it matters |
|---|---|
| `Cantor8/docs` | MDX docs for **Wallet SDK**, **Token Factory**, Enterprise Wallet, Validator-as-a-Service. There is a real TS SDK (`C8WalletProvider`) — you do not have to hand-roll everything. |
| `Cantor8/splice-fork` | Scala. Reference apps for funding/operating incentives. |
| `Cantor8/rust-daml-bindings` | Rust Daml codegen + bindings. |
| `Cantor8/canton-dev-fund` | Governance/funding proposals. |

---

## 2. The challenges, and how they are scored

Three tracks you pick from; four "accelerator problems" explicitly bigger than a day.

- **A1 — Build a scanner.** Canton has no block explorer *and cannot have one*: a
  node only holds data for parties it hosts. Read the ACS for balances, then
  stream forward, persist, serve, and resume after a kill.
- **A2 — Ledger vs database drift.** Hold one invariant, check it continuously,
  act on drift, expose metrics. They will inject drift in front of you.
- **D1 — Spend-limited wallet for an AI agent.** Cap, allow-list, expiry,
  instant revocation, audit trail — **enforced in Daml, not in your backend**.
- **N1 — No-code argument.** One use case that needs privacy *and* cross-org
  atomic settlement simultaneously. Three pages or a three-minute video.

**Accelerator:** holding management under load (UTXO coin selection), Token
Standard V2, on-chain governance for a token.

### The rubric (this is the part people skip)

| Criterion | Weight |
|---|---|
| Does it measure the thing? | 30% |
| Does it survive an attack? | 25% |
| Does it work outside the demo? | 20% |
| Is the honesty good? | 15% |
| Would this ship? | 10% |

Three things follow directly from that table:

1. **Bring a number.** A demo with no measurement scores badly however nice it looks.
2. **They will attack it.** Exceed the cap, kill the process mid-flight, observe
   something you should not see. Attack your own work first.
3. **Say what is mocked.** Overclaiming is penalised harder than an incomplete build.

---

## 3. Canton mental model — the four things that actually bite

**Your balance is a set of contracts, not a number.** Holdings are UTXOs. A
transfer archives the ones it spends and creates change. Two concurrent transfers
can grab the same holding; one loses with `LOCAL_VERDICT_LOCKED_CONTRACTS`.

**`Holding` is a Daml *interface*, not a template.** A `TemplateFilter` matches
nothing and returns `200 OK` with an empty list — indistinguishable from a zero
balance. Use `InterfaceFilter` + `includeInterfaceView: true` on
`#splice-api-token-holding-v1:Splice.Api.Token.HoldingV1:Holding`.

**A transfer is two phases.** Privacy means you cannot see the issuer's config
contracts, so you ask the registry for a factory *and* a choice context, and
attach what it returns as **disclosed contracts**. You cannot build the transfer
by hand — that is the design, not a toolkit limitation.

**`transferKind` decides whether money actually moved.**
`direct` = receiver had a live preapproval, funds moved.
`offer` = a `TransferInstruction` was created and the receiver must accept;
their balance does not change until they do. `self` = same party.

Also: a token proves *who you are*; it grants **no rights over a party**. That is
a separate `CanActAs` grant, and it is the #1 time-waster (403 with a valid token).

---

## 4. DevNet: measured state

Working config — the last two are **not optional and the README does not say so**:

```bash
export C8_BASE=https://api.validator.dev.digik.cantor8.tech/api/ledger
export C8_IDP=https://auth.dev.digik.cantor8.tech
export C8_CLIENT_ID=hackathon
export C8_CLIENT_SECRET=<secret>          # in ../.env, NOT in the repo
export C8_REGISTRY=https://sv-proxy.dev.digik.cantor8.tech
export C8_ADMIN_PARTY=DSO::1220be58c29e65de40bf273be1dc2b266d43a9a002ea5b18955aeef7aac881bb471a
```

Confirmed working: token issue (200), `/v2/state/ledger-end` (offset 2,918,048),
`/v2/parties` (200), `/v2/state/active-contracts` (200).

### Five measured breakages in `c8lab.py` on DevNet

1. **Token lives 900s; `token()` never refreshes.** `_tok["t"]` is cached forever
   on the `IDP` path. Any streaming service 401s at minute 15 — and A1 *requires*
   a continuously streaming service. This will read as a streaming bug.
2. **`dso_party()` fails.** Its error says "wait and retry"; waiting never helps.
   Breaks lab steps 3 and 6. Fix: set `C8_ADMIN_PARTY` (verified, instant).
3. **`/v2/parties` is paginated; `parties()` reads only page 1.** 10,000 returned,
   5,784 `isLocal`, plus a `nextPageToken` that is never followed. Root cause of #2.
4. **`check()` needs ≥13 min.** It loops all 5,784 parties with one ACS call each.
   Floor, extrapolated from one *empty*-ACS call at 0.13s. "Run check first" does
   not hold on DevNet.
5. **This credential is rejected by the scanner API** (401). Its `aud` covers the
   ledger and validator APIs only. Whether another client exists is **unknown** —
   one negative result, not proof. Ask Davide.

Also: on the `IDP` path `token(sub)` **ignores `sub`** — `sub=ADMIN` and `sub=USER`
are the same identity (`validator-backend@clients`), while `submit()` still writes
`userId: sub` into the body. LocalNet and DevNet differ here.

### Open with no credentials at all

| URL | Gives you |
|---|---|
| `sv-proxy.../registry/metadata/v1/info` | the DSO party id |
| `sv-proxy.../registry/metadata/v1/instruments` | Amulet + supported API versions |
| `sv-proxy.../api/scan/v0/scans` | every SV scan node |
| `token-registry.../api/c8/registry/metadata/v1/*` | the Cantor8 tokens |
| `scanner-ledger-read-api.../health` | index lag + stream staleness |

### Two registries, two admins (measured)

| | Amulet (Canton Coin) | Cantor8 tokens |
|---|---|---|
| Base | `sv-proxy.dev.digik.cantor8.tech` | `token-registry.dev.digik.cantor8.tech` |
| Path prefix | none | `/api/c8` |
| Admin party | `DSO::1220be58c2…` | `cantor8-digik-1::12204e94c0e449c0efcd270dd1e68259c36471cebef132e5c7dfc2750fe8c9eed77f` |
| Instruments | `Amulet` (supply 8.42e22) | `c8ETH` (dec 10), `c8BTC` (dec 8), `c8TEST` (dec 10), `rCC` (dec 10) |

**Amulet on DevNet already serves the full Token Standard V2 surface** —
`transfer-instruction-v2`, `holding-v2`, `allocation-v2`, `allocation-instruction-v2`,
`transfer-events-v2` — *and* still serves v1. The c8 tokens are v1 + `allocation-v1`
only (`rCC` has no allocation support at all).

That makes Amulet a live, working V2 reference you can read against — directly
relevant to the Token Standard V2 accelerator problem.

**Useful trick:** POST an empty `{"choiceArguments":{}}` to a registry factory
endpoint. It 400s with the exact missing field, so the registry documents its own
schema. v1 wants `expectedAdmin` at the top level; v2 wants `transfer`.

---

## 5. Environment (measured on this machine)

Present: `python3` 3.13.5, `docker` 29.6.2, `java` 21.0.12, `node` v22.23.1,
`gh` 2.83.2 (authed as `aswin-giridhar`), `curl` 8.12.1.
**Absent: `daml`** — the Daml track needs `sh get-daml.sh 3.4.10` first (pinned;
the Assistant is removed in SDK 3.5). LocalNet is not running (nothing on :2975).

`daml test` runs in memory in ~1s with no node and no Docker — that is the dev loop.

### Housekeeping

Credentials live in a `.env` at the repository root, outside the
toolkit repo so they cannot be committed upstream. **`/mnt/<drive>` is a DrvFs mount and
ignores POSIX modes**, so the `chmod 600` did not stick. Consider moving the file
to the Linux filesystem (e.g. `~/.canton8.env`) if that matters.

Also note: `/mnt/*` never fires inotify, so file-watching dev tools (vite, nodemon,
`tsc --watch`) will not see edits. Use polling or restart.

---

## 6. Known doc/code drift in the toolkit

- README's function table says `create_preapproval(me, provider)`; the real symbol
  is `create_preapproval_proposal`.
- `Mandate.daml`'s header cites challenges "D3 / D4"; the current file has only D1.
- `find_party` has an unreachable fallback: `"…" + "\n  ".join(...) or "  (none)"`
  — `+` binds tighter than `or`, so with zero parties it prints a dangling
  `Local parties:` and no `(none)`.

Worth crediting: `check()` prints an explicit **"NOT checked"** list. The repo
practises the rubric's honesty criterion on itself.

---

## 7. Environment state — verified 29 Aug, 13:40

**Daml SDK 3.4.10 installed** at `~/.daml` (Linux x86_64; the Rosetta step in
SETUP.md is macOS-only and does not apply here).

```bash
export PATH="$HOME/.daml/bin:$PATH"
```

Working copy at `agent-mandate/` (a copy of `daml-starter`, renamed in `daml.yaml`).
**The upstream `hackathon-toolkit/` tree is untouched — `git status` clean.**

Verified green, matching the starter README's documented output exactly:

```
daml/Test.daml:testIou:     ok, 1 active contracts,  4 transactions.
daml/Test.daml:testMandate: ok, 0 active contracts, 10 transactions.
exit 0     build ~19s, test ~19s (on the /mnt/<drive> Windows mount)
```

Two things the build told us that are worth keeping:

- **Choice coverage is 50%** — 10 internal template choices defined, 5 exercised.
  `submitMustFail` does not count as exercising a choice. Raising this is a cheap,
  quotable metric for the "does it measure the thing" criterion.
- **`daml build` warns that templates depending on `daml-script` bloat the package
  store** on upload. Recommended fix is to split tests into a separate package.
  Harmless for `daml test`; matters if we ever upload the DAR to a participant.

Expected, ignorable: the DPM deprecation warning, and the `submitMulti` deprecation
in `Test.daml:55` (legacy API; `submit` + `actAs` is the modern form).
