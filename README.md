# Canton hackathon London 2026 - Cantor8

Team working repo. **Track: D1 - a spend-limited wallet for an AI agent.**

**Live demo and pitch: https://frontend-pi-nine-95.vercel.app**

## The idea, in one sentence

> AP2 defines agent spending mandates, but its defence against a prompt-injected
> agent is a rule asking that same agent to behave. We make the mandate a **ledger
> invariant** instead — so a genuinely compromised agent still cannot exceed its
> cap, pay an unapproved counterparty, or spend after revocation.

## Read in this order

| File | What |
|---|---|
| [`context/00-canton8-hackathon-context.md`](context/00-canton8-hackathon-context.md) | **Start here.** Measured DevNet state, working config, five breakages in the upstream toolkit, environment setup. |
| [`context/02-d1-research-and-strategy.md`](context/02-d1-research-and-strategy.md) | Why this project. Cantor8's p402 roadmap, the AP2 circularity, the attack matrix, domain options. |
| [`context/03-d1-team-plan.md`](context/03-d1-team-plan.md) | **Who does what.** Four workstreams split by tool capacity, dependency graph, cut list. |
| [`context/01-brainstorm-api-and-daml.md`](context/01-brainstorm-api-and-daml.md) | Background: both tracks compared, before we picked D1. |
| [`devnet-findings.md`](devnet-findings.md) | The DevNet bug report, standalone. Shareable with the organisers. |
| [`STATUS.md`](STATUS.md) | **Current state.** What is proven, what is mocked, what is pending. |
| [`token-standard/`](token-standard/) | Real Canton Coin moving through the mandate. |
| [`frontend/`](frontend/) | The deployed site: live mandate page + the pitch deck. Press Space to step through the attacks. |

## Setup

```bash
cp example.env .env        # then paste the client secret from the team
set -a; . ./.env; set +a
```

`.env` is gitignored and must stay that way — it holds a live shared credential.

Daml (needed for `agent-mandate/`):

```bash
curl -sSL https://get.daml.com/ -o get-daml.sh && sh get-daml.sh 3.4.10
export PATH="$HOME/.daml/bin:$PATH"
cd agent-mandate && daml build && daml test
```

Verified green on SDK 3.4.10 — both tests pass in ~19s, no node or network needed.
`daml test` is the development loop.

## Three things that will waste your time if you don't know them

1. **The DevNet token expires in 900 seconds** and the upstream `c8lab.py` never
   refreshes it. Anything long-running 401s at minute 15 and looks like a
   different bug entirely.
2. **`C8_ADMIN_PARTY` and `C8_REGISTRY` are not optional on DevNet**, and the
   upstream README does not say so. Without them, lab steps 3 and 6 fail.
3. **`Holding` is a Daml interface, not a template.** A `TemplateFilter` returns
   `200 OK` with an empty list, which is indistinguishable from a zero balance.

## Layout

```
context/           the thinking - read these first
agent-mandate/     the Daml contracts (templates only)
agent-mandate-tests/  24 scripts: attacks, properties, coverage
agent-wallet/      MCP wallet server + attack harnesses
token-standard/    real Canton Coin through the mandate
frontend/          the demo page
deck/              the pitch deck
STATUS.md          what is proven vs mocked vs pending
devnet-findings.md standalone bug report for the organisers
example.env        template; copy to .env and fill in
```

`hackathon-toolkit/` (the upstream Cantor8 repo) is deliberately **not** committed
here — clone it separately from `github.com/Cantor8/hackathon-toolkit`.
