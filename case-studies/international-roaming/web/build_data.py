"""Regenerates data.json for The Scenario Explorer from the case study's
notebook outputs.

Run from the international-roaming/ directory (one level up from web/),
after 01-04 have been executed in order:

    cd case-studies/international-roaming
    python web/build_data.py

Reads the same aggregate tables notebook 04's Power BI export uses
(data/synthetic/simulation_price_sweep.parquet, simulation_scenarios.parquet,
data/powerbi/fact_segment_revenue.parquet, dim_segment.parquet) and writes
web/data.json — the only file index.html fetches at runtime.
"""

import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent  # international-roaming/
OUT = Path(__file__).resolve().parent / "data.json"  # web/data.json


def main():
    sweep = pd.read_parquet(BASE / "data/synthetic/simulation_price_sweep.parquet")
    scen = pd.read_parquet(BASE / "data/synthetic/simulation_scenarios.parquet")
    seg_rev = pd.read_parquet(BASE / "data/powerbi/fact_segment_revenue.parquet")
    dim_seg = pd.read_parquet(BASE / "data/powerbi/dim_segment.parquet")

    grid = sorted(sweep["price_multiplier"].unique().tolist())

    # population sweep: as fitted / conservative, p5/median/p95 per price
    pop = {}
    for case in ["as fitted", "conservative"]:
        d = sweep[sweep["case"] == case].sort_values("price_multiplier")
        pop[case] = {
            "price": d["price_multiplier"].round(3).tolist(),
            "p5": d["p5"].round(0).astype(int).tolist(),
            "median": d["median"].round(0).astype(int).tolist(),
            "p95": d["p95"].round(0).astype(int).tolist(),
        }

    # macro scenarios: contraction/base/expansion at 1.0/1.1/1.2
    macro = {}
    for s in ["contraction", "base", "expansion"]:
        d = scen[scen["scenario"] == s].sort_values("price")
        macro[s] = {
            "price": d["price"].round(2).tolist(),
            "p5": d["p5"].round(0).astype(int).tolist(),
            "median": d["median"].round(0).astype(int).tolist(),
            "p95": d["p95"].round(0).astype(int).tolist(),
        }

    # segments: non-dormant, % change vs the price=1.0 baseline, ranked by revenue share
    dim_seg_nd = dim_seg[~dim_seg["is_dormant"]].sort_values("rev_share", ascending=False)
    seg_order = dim_seg_nd["segment"].tolist()

    segments = {}
    for seg_name in seg_order:
        d = seg_rev[seg_rev["segment"] == seg_name].sort_values("price_multiplier")
        base_rev = float(d.loc[d["price_multiplier"] == 1.0, "revenue"].iloc[0])
        segments[seg_name] = {
            "price": d["price_multiplier"].round(3).tolist(),
            "revenue": d["revenue"].round(0).astype(int).tolist(),
            "pct": ((d["revenue"] / base_rev - 1) * 100).round(2).tolist(),
        }

    seg_meta = {}
    for _, r in dim_seg_nd.iterrows():
        seg_meta[r["segment"]] = {
            "headline": r["headline"],
            "description": r["description"],
            "accounts": int(r["accounts"]),
            "acct_share": round(float(r["acct_share"]), 4),
            "rev_share": round(float(r["rev_share"]), 4),
            "business": round(float(r["business"]), 4),
            "rev_per_acct": round(float(r["rev_per_acct"]), 2),
        }

    assump = pd.read_parquet(BASE / "data/powerbi/dim_assumption.parquet").set_index("assumption")["value"]

    payload = {
        "grid": [round(g, 3) for g in grid],
        "pop": pop,
        "macro": macro,
        "segments": segments,
        "segMeta": seg_meta,
        "segOrder": seg_order,
        "assumptions": {
            "response_ratio": round(float(assump.get("response scale (conservative)")), 3),
            "depth_bias": round(float(assump.get("depth bias (conservative)")), 3),
        },
    }

    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
