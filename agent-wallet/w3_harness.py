#!/usr/bin/env python3
"""W3 measurement and attack harness for the agent-mandate wallet.

Runs against a real JSON Ledger API v2 endpoint (normally daml sandbox), never
a fake ledger. It retains verbatim HTTP error bodies in JSON and generates a
compact Markdown scorecard. No third-party Python dependencies are required.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable

import ledger as L

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MANDATE_SOURCE = ROOT / "agent-mandate" / "daml" / "Mandate.daml"


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lo, hi = math.floor(index), math.ceil(index)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def latency_stats(values: list[float]) -> dict:
    return {
        "count": len(values),
        "min_ms": min(values, default=0.0),
        "mean_ms": statistics.fmean(values) if values else 0.0,
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "max_ms": max(values, default=0.0),
    }


def source_line(needle: str, occurrence: int = 1) -> dict:
    seen = 0
    for number, text in enumerate(MANDATE_SOURCE.read_text().splitlines(), 1):
        if needle in text:
            seen += 1
            if seen == occurrence:
                return {
                    "file": str(MANDATE_SOURCE.relative_to(ROOT)),
                    "line": number,
                    "code": text.strip(),
                }
    raise RuntimeError(f"Daml provenance text not found: {needle}")


@dataclass
class Fixture:
    owner: str
    agent: str
    merchant: str
    mallory: str
    mandate: str


def parties() -> tuple[str, str, str, str]:
    return tuple(L.allocate_party(name) for name in (
        "w3-alice", "w3-agent", "w3-merchant", "w3-mallory"))


def new_fixture(*, cap="100.0", expired=False) -> Fixture:
    owner, agent, merchant, mallory = parties()
    now = dt.datetime.now(dt.timezone.utc)
    expiry = now - dt.timedelta(minutes=1) if expired else now + dt.timedelta(days=1)
    made = L.create(L.MANDATE_PROPOSAL, {
        "owner": owner,
        "spender": agent,
        "cap": cap,
        "allowedCounterparties": [merchant],
        "expiresAt": iso(expiry),
    }, act_as=owner)
    proposal = L.first_created(made, "MandateProposal")
    accepted = L.exercise(L.MANDATE_PROPOSAL, proposal, "Accept", {},
                          act_as=agent)
    mandate = (L.first_created(accepted, "Mandate:Mandate")
               or L.first_created(accepted, "Mandate"))
    if not mandate:
        raise RuntimeError("fixture creation returned no Mandate contract id")
    return Fixture(owner, agent, merchant, mallory, mandate)


def exercise(f: Fixture, cid: str, choice: str, argument: dict, actor: str):
    return L.exercise(L.MANDATE, cid, choice, argument, act_as=actor)


def charge(f: Fixture, cid: str, amount: str, receiver: str):
    return exercise(f, cid, "Charge", {
        "amount": amount, "receiver": receiver, "purse": None,
    }, f.agent)


@dataclass
class Attack:
    name: str
    source_needle: str
    expected: tuple[str, ...]
    attempt: Callable[[], None]
    source_occurrence: int = 1


def attack_cases() -> list[Attack]:
    def unapproved():
        f = new_fixture()
        charge(f, f.mandate, "1.0", f.mallory)

    def over_cap():
        f = new_fixture()
        first = charge(f, f.mandate, "90.0", f.merchant)
        successor = L.first_created(first, "Mandate:Mandate")
        charge(f, successor, "20.0", f.merchant)

    def negative():
        f = new_fixture()
        charge(f, f.mandate, "-50.0", f.merchant)

    def expired():
        f = new_fixture(expired=True)
        charge(f, f.mandate, "1.0", f.merchant)

    def replay():
        f = new_fixture()
        charge(f, f.mandate, "10.0", f.merchant)
        charge(f, f.mandate, "10.0", f.merchant)

    def raise_cap():
        f = new_fixture()
        exercise(f, f.mandate, "Adjust", {"newCap": "1000000.0"}, f.agent)

    def after_revoke():
        f = new_fixture()
        exercise(f, f.mandate, "Revoke", {}, f.owner)
        charge(f, f.mandate, "1.0", f.merchant)

    def owner_charges():
        f = new_fixture()
        exercise(f, f.mandate, "Charge", {
            "amount": "1.0", "receiver": f.merchant, "purse": None,
        }, f.owner)

    def stranger_charges():
        f = new_fixture()
        exercise(f, f.mandate, "Charge", {
            "amount": "1.0", "receiver": f.merchant, "purse": None,
        }, f.mallory)

    def widen_restrict():
        f = new_fixture()
        exercise(f, f.mandate, "Restrict", {
            "newCap": "1000.0", "newAllowed": [f.merchant],
        }, f.owner)

    def add_payee():
        f = new_fixture()
        exercise(f, f.mandate, "Restrict", {
            "newCap": "100.0", "newAllowed": [f.merchant, f.mallory],
        }, f.owner)

    def agent_restricts():
        f = new_fixture()
        exercise(f, f.mandate, "Restrict", {
            "newCap": "100.0", "newAllowed": [f.merchant],
        }, f.agent)

    inactive = ("inactive", "not active", "could not be found", "not found")
    unauthorized = ("authorization", "authoriz", "controller")
    return [
        Attack("unapproved counterparty", "counterparty is not on the allow-list",
               ("counterparty is not on the allow-list",), unapproved),
        Attack("exceed cap", "charge would exceed the cap",
               ("charge would exceed the cap", "failed to create"), over_cap),
        Attack("negative amount", "amount must be positive",
               ("amount must be positive", "failed to create"), negative),
        Attack("spend after expiry", 'assertMsg "mandate expired"',
               ("mandate expired",), expired),
        Attack("replay consumed mandate", "choice Charge :", inactive, replay),
        Attack("agent raises own cap", "controller owner, spender",
               unauthorized, raise_cap),
        Attack("spend after revocation", "choice Revoke :", inactive, after_revoke),
        Attack("owner uses spender Charge", "controller spender", unauthorized,
               owner_charges),
        Attack("stranger charges", "controller spender",
               inactive + unauthorized, stranger_charges),
        Attack("Restrict widens cap", "Restrict may only lower the cap",
               ("Restrict may only lower the cap",), widen_restrict),
        Attack("Restrict adds counterparty", "Restrict may only remove counterparties",
               ("Restrict may only remove counterparties",), add_payee),
        Attack("agent invokes owner Restrict", "controller owner", unauthorized,
               agent_restricts, source_occurrence=3),
    ]


def run_attacks() -> list[dict]:
    rows = []
    for case in attack_cases():
        started = time.perf_counter()
        try:
            case.attempt()
        except L.LedgerError as error:
            elapsed = (time.perf_counter() - started) * 1000
            haystack = (str(error) + "\n" + error.raw_detail).lower()
            matched = next((item for item in case.expected
                            if item.lower() in haystack), None)
            rows.append({
                "attack": case.name,
                "blocked": True,
                "expected_reason_matched": bool(matched),
                "matched": matched,
                "reason": str(error),
                "http_status": error.status,
                "verbatim_ledger_error": error.raw_detail,
                "latency_ms": elapsed,
                "daml": source_line(case.source_needle,
                                    case.source_occurrence),
            })
        except Exception as error:
            rows.append({
                "attack": case.name, "blocked": False,
                "expected_reason_matched": False,
                "reason": f"HARNESS ERROR: {type(error).__name__}: {error}",
                "verbatim_ledger_error": "", "http_status": None,
                "latency_ms": (time.perf_counter() - started) * 1000,
                "daml": source_line(case.source_needle,
                                    case.source_occurrence),
            })
        else:
            rows.append({
                "attack": case.name, "blocked": False,
                "expected_reason_matched": False,
                "reason": "ATTACK SUCCEEDED", "verbatim_ledger_error": "",
                "http_status": None,
                "latency_ms": (time.perf_counter() - started) * 1000,
                "daml": source_line(case.source_needle,
                                    case.source_occurrence),
            })
    return rows


def one_concurrency_run(run_number: int) -> dict:
    # Each request is independently valid against the initial state, but both
    # succeeding would spend 2.0 against a cap of 1.0. The consuming Mandate
    # must serialize the race: one commit, one contention abort.
    f = new_fixture(cap="1.0")
    gate = threading.Barrier(2)

    def submit(worker: int) -> dict:
        gate.wait()
        started = time.perf_counter()
        try:
            charge(f, f.mandate, "1.0", f.merchant)
            return {"worker": worker, "outcome": "success",
                    "latency_ms": (time.perf_counter() - started) * 1000}
        except L.LedgerError as error:
            raw = (str(error) + "\n" + error.raw_detail).lower()
            contention_markers = (
                "locked_contract", "locked contract", "inactive",
                "not active", "could not be found", "not found",
                "dependency_error", "contract_not_active",
            )
            is_contention = any(marker in raw for marker in contention_markers)
            return {"worker": worker,
                    "outcome": ("contention_abort" if is_contention
                                else "infrastructure_error"),
                    "latency_ms": (time.perf_counter() - started) * 1000,
                    "reason": str(error), "http_status": error.status,
                    "verbatim_ledger_error": error.raw_detail}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, (1, 2)))
    successes = sum(r["outcome"] == "success" for r in results)
    aborts = sum(r["outcome"] == "contention_abort" for r in results)
    infra = sum(r["outcome"] == "infrastructure_error" for r in results)
    return {"run": run_number, "successes": successes, "aborts": aborts,
            "infrastructure_errors": infra,
            "exactly_one_won": successes == 1 and aborts == 1 and infra == 0,
            "attempts": results}


def run_concurrency(count: int) -> dict:
    runs = []
    for number in range(1, count + 1):
        try:
            runs.append(one_concurrency_run(number))
        except L.LedgerError as error:
            # Fixture/setup failures are infrastructure failures, not evidence
            # that contention stopped a charge.
            runs.append({
                "run": number, "successes": 0, "aborts": 0,
                "infrastructure_errors": 1, "exactly_one_won": False,
                "attempts": [{"worker": None,
                              "outcome": "infrastructure_error",
                              "reason": str(error),
                              "http_status": error.status,
                              "verbatim_ledger_error": error.raw_detail}],
            })
    attempts = [a for run in runs for a in run["attempts"]]
    return {
        "runs_requested": count,
        "runs_exactly_one_won": sum(r["exactly_one_won"] for r in runs),
        "total_attempts": len(attempts),
        "successes": sum(a["outcome"] == "success" for a in attempts),
        "aborts": sum(a["outcome"] == "contention_abort" for a in attempts),
        "infrastructure_errors": sum(
            a["outcome"] == "infrastructure_error" for a in attempts),
        "success_latency": latency_stats([
            a["latency_ms"] for a in attempts if a["outcome"] == "success"]),
        "abort_latency": latency_stats([
            a["latency_ms"] for a in attempts
            if a["outcome"] == "contention_abort"]),
        "daml": source_line("choice Charge :"),
        "runs": runs,
    }


def run_sequential_charges(count: int) -> dict:
    f = new_fixture(cap=str(max(count + 1, 2)) + ".0")
    cid = f.mandate
    latencies = []
    failures = []
    for number in range(1, count + 1):
        started = time.perf_counter()
        try:
            result = charge(f, cid, "1.0", f.merchant)
            elapsed = (time.perf_counter() - started) * 1000
            cid = L.first_created(result, "Mandate:Mandate")
            if not cid:
                raise RuntimeError("charge returned no successor Mandate")
            latencies.append(elapsed)
        except Exception as error:
            failures.append({"charge": number, "reason": str(error)})
            break
    return {"requested": count, "executed_end_to_end": len(latencies),
            "failures": failures, "latency": latency_stats(latencies)}


def run_daml_tests(skip: bool) -> dict:
    if skip:
        return {"skipped": True}
    env = os.environ.copy()
    daml = str(Path.home() / ".daml" / "bin" / "daml")
    if not Path(daml).exists():
        daml = "daml"
    build = subprocess.run(
        [daml, "build"], cwd=ROOT / "agent-mandate",
        env=env, text=True, capture_output=True)
    if build.returncode != 0:
        return {"skipped": False, "passed": False, "runtime_seconds": 0,
                "output": build.stdout + build.stderr,
                "reason": "template build failed before timed test"}
    started = time.perf_counter()
    test = subprocess.run(
        [daml, "test", "--all"], cwd=ROOT / "agent-mandate-tests",
        env=env, text=True, capture_output=True)
    elapsed = time.perf_counter() - started
    return {"skipped": False, "passed": test.returncode == 0,
            "runtime_seconds": elapsed,
            "output": test.stdout + test.stderr}


def compact_reason(value: str) -> str:
    value = " ".join(value.split())
    return value[:137] + "..." if len(value) > 140 else value


def markdown(results: dict) -> str:
    attacks = results["attacks"]
    concurrency = results["concurrency"]
    sequential = results["sequential_charges"]
    tests = results["daml_tests"]
    good_attacks = sum(a["blocked"] and a["expected_reason_matched"]
                       for a in attacks)
    integrity = (good_attacks == len(attacks)
                 and concurrency["runs_exactly_one_won"] == concurrency["runs_requested"]
                 and sequential["executed_end_to_end"] == sequential["requested"]
                 and (tests.get("skipped") or tests.get("passed")))
    lines = [
        "# W3 — measured results", "",
        f"Generated `{results['generated_at']}` against `{results['ledger']}`. ",
        f"Overall harness verdict: **{'PASS' if integrity else 'FAIL'}**.", "",
        "## Scorecard", "",
        "| Measurement | Result |", "|---|---|",
        f"| Attack rules rejected for the expected reason | **{good_attacks}/{len(attacks)}** |",
        f"| Concurrency runs with exactly 1 success + 1 abort | **{concurrency['runs_exactly_one_won']}/{concurrency['runs_requested']}** |",
        f"| Concurrent submissions | {concurrency['total_attempts']} ({concurrency['successes']} success, {concurrency['aborts']} contention abort, {concurrency['infrastructure_errors']} infrastructure error) |",
        f"| Successful-charge latency | p50 **{concurrency['success_latency']['p50_ms']:.1f} ms**, p95 **{concurrency['success_latency']['p95_ms']:.1f} ms** |",
        f"| Sequential charges end-to-end | **{sequential['executed_end_to_end']}/{sequential['requested']}** |",
        f"| Sequential charge latency | mean **{sequential['latency']['mean_ms']:.1f} ms**, p50 **{sequential['latency']['p50_ms']:.1f} ms**, p95 **{sequential['latency']['p95_ms']:.1f} ms** |",
        (f"| `daml test --all` | **{'PASS' if tests.get('passed') else 'FAIL'}**, {tests.get('runtime_seconds', 0):.2f} s |"
         if not tests.get("skipped") else "| `daml test --all` | skipped by flag |"),
        "| Token refresh | refresh-before-expiry + one retry on 401; concurrent refresh unit-tested |",
        "", "## Attack matrix", "",
        "| Attack | Verdict | Ledger reason (compact) | Daml source |",
        "|---|---|---|---|",
    ]
    for row in attacks:
        verdict = "BLOCKED (expected rule)" if (
            row["blocked"] and row["expected_reason_matched"]) else "FAIL"
        src = row["daml"]
        reason = compact_reason(row["reason"]).replace("|", "\\|")
        code = src["code"].replace("|", "\\|")
        lines.append(
            f"| {row['attack']} | {verdict} | `{reason}` | "
            f"`{src['file']}:{src['line']}` — `{code}` |")
    lines += [
        "", "## Interpretation", "",
        "Each race submitted two `Charge` exercises against the same immutable Mandate contract id. A consuming choice permits only one transaction to consume that contract; the other submission must abort. The successor mandate is not shared with the losing command, so aggregate spend cannot be lost through a read/check/write race.",
        "",
        "The Markdown table compacts errors for readability. `w3-results.json` retains every HTTP error body verbatim, along with per-attempt timings and all concurrency outcomes.",
        "",
        "## Scope", "",
        "These measurements use the project `Purse`/`Mandate` model on a real local Canton sandbox. They do not claim a funded token-standard transfer or a DevNet concurrency result.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--concurrency-runs", type=int, default=20)
    parser.add_argument("--latency-charges", type=int, default=20)
    parser.add_argument("--skip-daml-tests", action="store_true")
    parser.add_argument("--json", type=Path, default=HERE / "w3-results.json")
    parser.add_argument("--markdown", type=Path,
                        default=HERE / "W3-RESULTS.md")
    args = parser.parse_args()
    if args.concurrency_runs < 1 or args.latency_charges < 1:
        parser.error("run counts must be positive")

    try:
        L.ledger_end()
    except L.LedgerError as error:
        print(f"Cannot start W3: {error}", file=sys.stderr)
        return 2

    results = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "ledger": L.BASE,
        "configuration": {
            "concurrency_runs": args.concurrency_runs,
            "latency_charges": args.latency_charges,
        },
    }
    started = time.perf_counter()
    print(f"W3: running {args.concurrency_runs} two-way contention races...",
          flush=True)
    results["concurrency"] = run_concurrency(args.concurrency_runs)
    print("W3: running 12 ledger attack cases...", flush=True)
    results["attacks"] = run_attacks()
    print(f"W3: timing {args.latency_charges} sequential charges...", flush=True)
    results["sequential_charges"] = run_sequential_charges(args.latency_charges)
    print("W3: timing Daml test suite...", flush=True)
    results["daml_tests"] = run_daml_tests(args.skip_daml_tests)
    results["harness_runtime_seconds"] = time.perf_counter() - started
    source = L._token_source()
    results["token_refreshes"] = source.refreshes if source else 0

    args.json.write_text(json.dumps(results, indent=2) + "\n")
    args.markdown.write_text(markdown(results))

    attacks_ok = all(a["blocked"] and a["expected_reason_matched"]
                     for a in results["attacks"])
    races_ok = (results["concurrency"]["runs_exactly_one_won"]
                == args.concurrency_runs)
    latency_ok = (results["sequential_charges"]["executed_end_to_end"]
                  == args.latency_charges)
    tests_ok = (results["daml_tests"].get("skipped")
                or results["daml_tests"].get("passed"))
    print(f"W3: wrote {args.markdown} and {args.json}")
    return 0 if attacks_ok and races_ok and latency_ok and tests_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
