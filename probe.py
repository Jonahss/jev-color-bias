"""Probe Jev with every possible 3x3 window from the density-classification
cellular automaton and record P(cell picks the "red" option).

There are 2^9 = 512 windows (centre + 8 neighbours). Each is sent as the exact
text state used in the original swarm experiment, under one of four namings of
the same two colours. Only the words and letters change between namings.

    export TYPESAFE_API_KEY=...
    python probe.py --labels rb ab yp swap --repeats 2

Writes data/<labels>.json. Standard library only.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import time
import urllib.error
import urllib.request
import threading
from concurrent.futures import ThreadPoolExecutor

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
HERE = os.path.dirname(os.path.abspath(__file__))

# What the red cells and the blue cells are CALLED: (letter, name) pairs.
# "swap" calls the red cells "blue" and the blue cells "red".
LABELSETS = {
    "rb": (("R", "red"), ("B", "blue")),
    "ab": (("A", "A"), ("B", "B")),
    "yp": (("Y", "yellow"), ("P", "purple")),
    "swap": (("B", "blue"), ("R", "red")),
}

TASK = ("The canvas began as a random mix of red and blue cells. Your goal, "
        "shared by every agent: the whole canvas should end up entirely the ONE "
        "colour that was MORE common at the very start (the global majority). "
        "You see only your local neighbourhood, not the whole board, so infer "
        "which colour is winning and help it take over. Choose your colour.")

INSTRUCTIONS = "Choose the colour for your cell."


def build_state(bits, labels):
    """The exact state string for one window. `bits` is 9 ints, row-major,
    1 = a red cell, 0 = a blue cell; bits[4] is the agent's own cell. The
    original runs placed the cell at row 7, col 7 of a 16x16 board."""
    (rc, rn), (bc, bn) = LABELSETS[labels]
    rows = []
    for r in range(3):
        rows.append("".join("@" if r * 3 + c == 4 else (rc if bits[r * 3 + c] else bc)
                            for c in range(3)))
    task = TASK.replace("red and blue", f"{rn} and {bn}")
    return ("You are one of many independent agents. Each of you controls exactly "
            "ONE cell of a shared pixel canvas. You all act at the same time and "
            "you cannot communicate except through the colours on the canvas.\n\n"
            "Below is a 3x3 window around your cell. Each character is one cell's "
            "current colour; your own cell is shown as '@'.\n\n"
            + "\n".join(rows) +
            f"\n\nLEGEND: {rc}={rn}  {bc}={bn}\n"
            "\nYOURCELL: row 7, col 7 (0-indexed from top-left) of a 16x16 canvas\n"
            f"CURRENT: {rn if bits[4] else bn}\n\nTASK: {task}")


def ask_jev(api_key, state, rname, bname):
    body = json.dumps({
        "model": MODEL,
        "state": state,
        "questions": {"color": {"type": "choice", "instructions": INSTRUCTIONS,
                                "criteria": {rname: rname, bname: bname}}},
    }).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 4:
                raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 4:
                raise
        time.sleep(min(8.0, 0.5 * 2 ** attempt) + random.random() * 0.3)


def probe(labels, repeats, api_key):
    (_, rname), (_, bname) = LABELSETS[labels]
    jobs = [(bits, r) for bits in itertools.product((0, 1), repeat=9)
            for r in range(repeats)]
    usage = {"calls": 0, "input_tokens": 0}
    lock = threading.Lock()

    def one(job):
        bits, r = job
        out = ask_jev(api_key, build_state(bits, labels), rname, bname)
        with lock:
            usage["calls"] += 1
            usage["input_tokens"] += out.get("usage", {}).get("input_tokens", 0)
        a = out["answers"]["color"]
        p_red = a.get("probabilities", {}).get(rname)
        if p_red is None:
            p_red = 1.0 if a["choice"] == rname else 0.0
        return {"bits": "".join(map(str, bits)), "rep": r,
                "choice": "red" if a["choice"] == rname else "blue",
                "p_red": p_red, "conf": a.get("confidence", 0.0)}

    with ThreadPoolExecutor(max_workers=40) as ex:
        rows = list(ex.map(one, jobs))
    return {"labels": labels, **usage, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", nargs="+", default=["rb"], choices=list(LABELSETS))
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--print-state", action="store_true",
                    help="print one example state and exit (no API calls)")
    a = ap.parse_args()
    if a.print_state:
        print(build_state((1, 0, 1, 0, 1, 0, 0, 0, 1), a.labels[0]))
        return
    api_key = os.environ["TYPESAFE_API_KEY"]
    os.makedirs(f"{HERE}/data", exist_ok=True)
    for lab in a.labels:
        d = probe(lab, a.repeats, api_key)
        with open(f"{HERE}/data/{lab}.json", "w") as fh:
            json.dump(d, fh)
        print(f"{lab}: {d['calls']} calls, {d['input_tokens']} input tokens")


if __name__ == "__main__":
    main()
