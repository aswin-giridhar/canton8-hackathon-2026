# Mandate — the demo site

Live: **https://frontend-pi-nine-95.vercel.app**

Two pages, one deployable static site:

| Page | What |
|---|---|
| `/` | **Live mandate** — the running state, and the attack sequence you drive |
| `/deck.html` | **The pitch** — nine slides. Prev/Next buttons, arrow keys, or Home/End |

Every figure on the dashboard is read back from a running Canton ledger.

## Demo it

```bash
cd frontend && python3 -m http.server 8899
# then open http://localhost:8899
```

**Driving it on stage:** click *Run the attack sequence*, or press `Space` to
step one attempt at a time and talk over each refusal. `R` resets. The counter
shows where you are, so you cannot lose your place mid-sentence.

The ledger snapshot is **inlined** in the page as well as served as
`ledger-snapshot.json` — a demo that needs a server is a demo that fails on
stage. Open the file directly and it still works. If the JSON is present and
newer, it wins.

## Refresh the data from a live ledger

```bash
cd hackathon-toolkit
python3 - <<'PY'   # see token-standard/ for the capture snippet
PY
cp ../token-standard/ledger-snapshot.json ../frontend/
```

## Design notes

The page splits into two material worlds, and that split is the argument:
**paper** holds the mandate and the audit ledger — what the ledger knows; the
**dark terminal** holds the agent's tool calls — what the agent tried. The agent
lives in one world and the authority lives in the other, and it cannot reach in.

The signature element is the refusal stamp: the actual Daml rule, stamped across
each blocked attempt with its `Mandate.daml` line number, because "show us the
line that stops it" is the question this project exists to answer.

Type is Instrument Serif for the thesis line only, with Public Sans and
JetBrains Mono carrying every data surface. Palette is ledger stock, ink, and a
single stamp red — no second accent.

Deliberate deviation: the MiniMax skill bans serif on dashboards. Kept for the
hero because the page is a pitch, not dashboard chrome; all data surfaces follow
the rule.

## Deploy

Static — no build step. `index.html`, `deck.html`, `ledger-snapshot.json`,
`vercel.json`. Any static host.

```bash
cd frontend && vercel deploy --prod --yes
```

The deck lives here rather than as a hosted artifact elsewhere, so the pitch
and the live demo ship together and share one URL.
