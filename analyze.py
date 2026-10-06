"""Reproduce the numbers in the README from data/<labels>.json.

    python analyze.py

For each naming it prints:
  - the colour-flip gap by window composition (the bias table),
  - how many of the 126 balanced window pairs lean each way,
  - the rule table P(pick the red cells' name) by neighbour count and centre.
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
# Name given to the red cells / blue cells under each naming.
NAMES = {"rb": ("red", "blue"), "swap": ("blue", "red"),
         "ab": ("A", "B"), "yp": ("yellow", "purple")}


def flip(bits):
    return "".join("1" if b == "0" else "0" for b in bits)


def load(labels):
    d = json.load(open(f"{HERE}/data/{labels}.json"))
    reps = defaultdict(list)
    for r in d["rows"]:
        reps[r["bits"]].append(r["p_red"])
    p = {k: sum(v) / len(v) for k, v in reps.items()}
    return d, reps, p


def main():
    total_calls = total_tokens = 0
    for labels in ("rb", "swap", "ab", "yp"):
        path = f"{HERE}/data/{labels}.json"
        if not os.path.exists(path):
            continue
        d, reps, p = load(labels)
        total_calls += d["calls"]
        total_tokens += d["input_tokens"]
        x, y = NAMES[labels]
        # gap(w) = P(X | w) - P(Y | flip w). Zero for a name-neutral model.
        gap = {w: p[w] - (1 - p[flip(w)]) for w in p}
        by_k = defaultdict(list)
        for w, g in gap.items():
            by_k[w.count("1")].append(g)
        print(f'== red cells called "{x}", blue cells called "{y}"')
        print("   gap by # of 9 cells that are X:  "
              + "  ".join(f"{k} of 9: {sum(by_k[k]) / len(by_k[k]):+.2f}" for k in (3, 4, 5, 6)))
        # balanced pairs: each 4-of-9 window with its 5-of-9 flipped twin
        pairs = [gap[w] for w in gap if w.count("1") == 4]
        favour_x = sum(g > 0 for g in pairs)
        favour_y = sum(g < 0 for g in pairs)
        n = len(pairs)
        lead, cnt = (x, favour_x) if favour_x >= favour_y else (y, favour_y)
        z = (cnt - n / 2) / math.sqrt(n / 4)
        print(f'   balanced pairs: {cnt} of {n} favour "{lead}" (z = {z:.1f} vs 50/50)')
        noise = [abs(v[0] - v[1]) for v in reps.values() if len(v) > 1]
        if noise:
            print(f"   repeat noise: mean |dp| = {sum(noise) / len(noise):.3f}")
        table = defaultdict(list)
        for w, v in p.items():
            table[(sum(int(b) for i, b in enumerate(w) if i != 4), w[4])].append(v)
        print(f'   P(pick "{x}") by # of X neighbours:')
        print("      neighbours: " + " ".join(f"{k:>5}" for k in range(9)))
        for c, name in (("0", f"centre {y:<6}"), ("1", f"centre {x:<6}")):
            print(f"   {name}: " + " ".join(
                f"{sum(table[(k, c)]) / len(table[(k, c)]):5.2f}" for k in range(9)))
        print()
    print(f"{total_calls} calls, {total_tokens} input tokens")


if __name__ == "__main__":
    main()
