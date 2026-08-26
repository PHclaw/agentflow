#!/usr/bin/env python3
"""Sample size calculator for proportion and mean experiments."""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any

from _stats_math import norm_ppf


def n_proportion(baseline: float, mde: float, alpha: float, power: float) -> dict[str, Any]:
    """mde is relative lift, e.g. 0.20 = +20% relative to baseline."""
    if not (0 < baseline < 1):
        raise ValueError("baseline must be in (0,1)")
    if mde <= 0:
        raise ValueError("mde must be > 0")
    if not (0 < alpha < 1) or not (0 < power < 1):
        raise ValueError("alpha/power must be in (0,1)")
    p1 = baseline
    p2 = baseline * (1 + mde)
    if not (0 < p2 < 1):
        raise ValueError("baseline*(1+mde) must be in (0,1)")
    z_a = norm_ppf(1 - alpha / 2)
    z_b = norm_ppf(power)
    num = (
        z_a * math.sqrt(2 * p1 * (1 - p1))
        + z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    den = (p2 - p1) ** 2
    n = math.ceil(num / den)
    return {
        "test": "sample_size_proportion",
        "baseline": baseline,
        "mde_relative": mde,
        "treatment_rate": p2,
        "absolute_lift_pp": (p2 - p1) * 100,
        "alpha": alpha,
        "power": power,
        "n_per_variant": n,
        "n_total": n * 2,
    }


def n_mean(
    baseline_mean: float,
    baseline_std: float,
    mde: float,
    alpha: float,
    power: float,
) -> dict[str, Any]:
    """mde is relative change in mean, e.g. 0.10 = +10%."""
    if baseline_std <= 0:
        raise ValueError("baseline-std must be > 0")
    if not (0 < alpha < 1) or not (0 < power < 1):
        raise ValueError("alpha/power must be in (0,1)")
    delta = abs(baseline_mean) * mde if baseline_mean != 0 else mde
    if delta == 0:
        raise ValueError("effect size delta is 0")
    z_a = norm_ppf(1 - alpha / 2)
    z_b = norm_ppf(power)
    n = math.ceil(2 * ((z_a + z_b) * baseline_std / delta) ** 2)
    return {
        "test": "sample_size_mean",
        "baseline_mean": baseline_mean,
        "baseline_std": baseline_std,
        "mde_relative": mde,
        "delta": delta,
        "alpha": alpha,
        "power": power,
        "n_per_variant": n,
        "n_total": n * 2,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--test", choices=["proportion", "mean"], required=True)
    p.add_argument("--baseline", type=float)
    p.add_argument("--mde", type=float, required=True)
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--power", type=float, default=0.80)
    p.add_argument("--baseline-mean", type=float)
    p.add_argument("--baseline-std", type=float)
    p.add_argument("--table", action="store_true")
    p.add_argument("--format", choices=["text", "json"], default="json")
    args = p.parse_args()
    try:
        if args.table:
            rows = []
            for power in (0.7, 0.8, 0.9):
                if args.test == "proportion":
                    if args.baseline is None:
                        raise ValueError("--baseline required")
                    rows.append(
                        n_proportion(args.baseline, args.mde, args.alpha, power)
                    )
                else:
                    if args.baseline_mean is None or args.baseline_std is None:
                        raise ValueError("--baseline-mean/std required")
                    rows.append(
                        n_mean(
                            args.baseline_mean,
                            args.baseline_std,
                            args.mde,
                            args.alpha,
                            power,
                        )
                    )
            result: Any = {"table": rows}
        elif args.test == "proportion":
            if args.baseline is None:
                raise ValueError("--baseline required")
            result = n_proportion(args.baseline, args.mde, args.alpha, args.power)
        else:
            if args.baseline_mean is None or args.baseline_std is None:
                raise ValueError("--baseline-mean/std required")
            result = n_mean(
                args.baseline_mean, args.baseline_std, args.mde, args.alpha, args.power
            )
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
