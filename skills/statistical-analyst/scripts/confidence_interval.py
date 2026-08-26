#!/usr/bin/env python3
"""Confidence intervals for a proportion or mean."""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any

from _stats_math import norm_ppf


def ci_proportion(n: int, x: int, confidence: float) -> dict[str, Any]:
    if n <= 0 or x < 0 or x > n:
        raise ValueError("invalid n/x")
    if not (0 < confidence < 1):
        raise ValueError("confidence must be in (0,1)")
    p = x / n
    z = norm_ppf(0.5 + confidence / 2)
    # Wilson score interval
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return {
        "type": "proportion",
        "n": n,
        "x": x,
        "rate": p,
        "confidence": confidence,
        "ci": [max(0.0, center - half), min(1.0, center + half)],
        "method": "wilson",
        "margin": half,
    }


def ci_mean(n: int, mean: float, std: float, confidence: float) -> dict[str, Any]:
    if n < 2 or std < 0:
        raise ValueError("invalid n/std")
    if not (0 < confidence < 1):
        raise ValueError("confidence must be in (0,1)")
    z = norm_ppf(0.5 + confidence / 2)
    se = std / math.sqrt(n)
    half = z * se
    return {
        "type": "mean",
        "n": n,
        "mean": mean,
        "std": std,
        "confidence": confidence,
        "ci": [mean - half, mean + half],
        "method": "normal_approx",
        "margin": half,
        "note": "Uses normal critical value; for small n prefer t critical",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["proportion", "mean"], required=True)
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--x", type=int)
    p.add_argument("--mean", type=float)
    p.add_argument("--std", type=float)
    p.add_argument("--confidence", type=float, default=0.95)
    p.add_argument("--format", choices=["text", "json"], default="json")
    args = p.parse_args()
    try:
        if args.type == "proportion":
            if args.x is None:
                raise ValueError("--x required for proportion")
            result = ci_proportion(args.n, args.x, args.confidence)
        else:
            if args.mean is None or args.std is None:
                raise ValueError("--mean and --std required")
            result = ci_mean(args.n, args.mean, args.std, args.confidence)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
