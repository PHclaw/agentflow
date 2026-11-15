#!/usr/bin/env python3
"""Hypothesis tests: z-test (proportions), Welch t-test (means), chi-square."""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any

from _stats_math import effect_label_cohen, effect_label_cramers_v, norm_cdf, norm_ppf


def _student_t_cdf(t: float, df: float) -> float:
    if df <= 0:
        raise ValueError("df must be > 0")
    x = df / (df + t * t)
    a = df / 2.0
    b = 0.5
    if x == 0:
        ibeta = 0.0
    elif x == 1:
        ibeta = 1.0
    else:

        def _betacf(aa: float, bb: float, xx: float) -> float:
            max_iter = 200
            eps = 3e-7
            am, bm = 1.0, 1.0
            az = 1.0
            qab = aa + bb
            qap = aa + 1.0
            qam = aa - 1.0
            bz = 1.0 - qab * xx / qap
            for m in range(1, max_iter + 1):
                em = float(m)
                tem = em + em
                d = em * (bb - em) * xx / ((qam + tem) * (aa + tem))
                ap = az + d * am
                bp = bz + d * bm
                d = -(aa + em) * (qab + em) * xx / ((aa + tem) * (qap + tem))
                app = ap + d * az
                bpp = bp + d * bz
                am, bm = ap / bpp, bp / bpp
                az, bz = app / bpp, 1.0
                if abs(az - am) < eps * abs(az):
                    return az
            return az

        try:
            bt = math.exp(
                math.lgamma(a + b)
                - math.lgamma(a)
                - math.lgamma(b)
                + a * math.log(x)
                + b * math.log(1 - x)
            )
            if x < (a + 1) / (a + b + 2):
                ibeta = bt * _betacf(a, b, x) / a
            else:
                ibeta = 1.0 - bt * _betacf(b, a, 1 - x) / b
        except (ValueError, OverflowError):
            return norm_cdf(t)
    if t >= 0:
        return 1.0 - 0.5 * ibeta
    return 0.5 * ibeta


def ztest(
    control_n: int,
    control_x: int,
    treatment_n: int,
    treatment_x: int,
    alpha: float = 0.05,
) -> dict[str, Any]:
    if min(control_n, treatment_n) <= 0:
        raise ValueError("sample sizes must be > 0")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be in (0,1)")
    if control_x < 0 or treatment_x < 0 or control_x > control_n or treatment_x > treatment_n:
        raise ValueError("success counts must be within [0, n]")
    p1 = control_x / control_n
    p2 = treatment_x / treatment_n
    p_pool = (control_x + treatment_x) / (control_n + treatment_n)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / control_n + 1 / treatment_n))
    z = 0.0 if se == 0 else (p2 - p1) / se
    p_value = 2 * (1 - norm_cdf(abs(z)))
    se_diff = math.sqrt(p1 * (1 - p1) / control_n + p2 * (1 - p2) / treatment_n)
    zcrit = norm_ppf(1 - alpha / 2)
    diff = p2 - p1
    h = 2 * math.asin(math.sqrt(p2)) - 2 * math.asin(math.sqrt(p1))
    return {
        "test": "ztest_proportions",
        "control_rate": p1,
        "treatment_rate": p2,
        "diff": diff,
        "diff_pp": diff * 100,
        "z": z,
        "p_value": p_value,
        "ci95_diff": [diff - zcrit * se_diff, diff + zcrit * se_diff],
        "effect_size_h": h,
        "effect_label": effect_label_cohen(h),
        "alpha": alpha,
        "significant": p_value < alpha,
    }


def ttest(
    control_mean: float,
    control_std: float,
    control_n: int,
    treatment_mean: float,
    treatment_std: float,
    treatment_n: int,
    alpha: float = 0.05,
) -> dict[str, Any]:
    if min(control_n, treatment_n) < 2:
        raise ValueError("n must be >= 2 per group")
    if control_std < 0 or treatment_std < 0:
        raise ValueError("std must be >= 0")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be in (0,1)")
    v1 = control_std**2
    v2 = treatment_std**2
    se = math.sqrt(v1 / control_n + v2 / treatment_n)
    diff = treatment_mean - control_mean
    t = 0.0 if se == 0 else diff / se
    num = (v1 / control_n + v2 / treatment_n) ** 2
    den = (v1 / control_n) ** 2 / (control_n - 1) + (v2 / treatment_n) ** 2 / (
        treatment_n - 1
    )
    df = num / den if den else float(control_n + treatment_n - 2)
    if df > 1000:
        p_value = 2 * (1 - norm_cdf(abs(t)))
    else:
        p_value = 2 * min(_student_t_cdf(-abs(t), df), 0.5)
        p_value = max(0.0, min(1.0, p_value))
    # Normal critical is fine for moderate/large n; documented in note
    zcrit = norm_ppf(1 - alpha / 2)
    pooled = math.sqrt(
        ((control_n - 1) * v1 + (treatment_n - 1) * v2)
        / max(control_n + treatment_n - 2, 1)
    )
    d = 0.0 if pooled == 0 else diff / pooled
    return {
        "test": "welch_ttest",
        "control_mean": control_mean,
        "treatment_mean": treatment_mean,
        "diff": diff,
        "t": t,
        "df": df,
        "p_value": p_value,
        "ci95_diff": [diff - zcrit * se, diff + zcrit * se],
        "effect_size_d": d,
        "effect_label": effect_label_cohen(d),
        "alpha": alpha,
        "significant": p_value < alpha,
        "note": "CI uses normal critical approx; suitable for moderate/large n",
    }


def chi2(observed: list[float], expected: list[float] | None = None, alpha: float = 0.05) -> dict[str, Any]:
    if not observed:
        raise ValueError("observed required")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be in (0,1)")
    if expected is None:
        mean = sum(observed) / len(observed)
        expected = [mean] * len(observed)
    if len(observed) != len(expected):
        raise ValueError("observed/expected length mismatch")
    if any(e <= 0 for e in expected):
        raise ValueError("expected counts must be > 0")
    stat = sum((o - e) ** 2 / e for o, e in zip(observed, expected))
    df = len(observed) - 1
    if df <= 0:
        p_value = 1.0
    else:
        z = ((stat / df) ** (1 / 3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
        p_value = max(0.0, min(1.0, 1 - norm_cdf(z)))
    n = sum(observed)
    k = len(observed)
    v = math.sqrt(stat / (n * (k - 1))) if n > 0 and k > 1 else 0.0
    return {
        "test": "chi_square",
        "chi2": stat,
        "df": df,
        "p_value": p_value,
        "cramers_v": v,
        "effect_label": effect_label_cramers_v(v),
        "observed": observed,
        "expected": expected,
        "alpha": alpha,
        "significant": p_value < alpha,
    }


def _parse_list(s: str) -> list[float]:
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def main() -> int:
    p = argparse.ArgumentParser(description="Hypothesis tester")
    p.add_argument("--test", choices=["ztest", "ttest", "chi2"], required=True)
    p.add_argument("--format", choices=["text", "json"], default="json")
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--control-n", type=int)
    p.add_argument("--control-x", type=int)
    p.add_argument("--treatment-n", type=int)
    p.add_argument("--treatment-x", type=int)
    p.add_argument("--control-mean", type=float)
    p.add_argument("--control-std", type=float)
    p.add_argument("--treatment-mean", type=float)
    p.add_argument("--treatment-std", type=float)
    p.add_argument("--observed", type=str)
    p.add_argument("--expected", type=str)
    args = p.parse_args()

    try:
        if args.test == "ztest":
            if None in (args.control_n, args.control_x, args.treatment_n, args.treatment_x):
                raise ValueError("ztest requires --control-n/x and --treatment-n/x")
            result = ztest(
                args.control_n,
                args.control_x,
                args.treatment_n,
                args.treatment_x,
                alpha=args.alpha,
            )
        elif args.test == "ttest":
            need = [
                args.control_mean,
                args.control_std,
                args.control_n,
                args.treatment_mean,
                args.treatment_std,
                args.treatment_n,
            ]
            if any(v is None for v in need):
                raise ValueError("ttest requires means, stds, and ns")
            result = ttest(
                args.control_mean,
                args.control_std,
                args.control_n,
                args.treatment_mean,
                args.treatment_std,
                args.treatment_n,
                alpha=args.alpha,
            )
        else:
            if not args.observed:
                raise ValueError("chi2 requires --observed")
            obs = _parse_list(args.observed)
            exp = _parse_list(args.expected) if args.expected else None
            result = chi2(obs, exp, alpha=args.alpha)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
