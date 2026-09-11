"""Regenerates data.json for the International Roaming Scenario Tool from the
case study's notebook exports.

Run from the international-roaming/ directory, after the notebook has been
re-executed (which refreshes data/synthetic/ and data/powerbi/):

    cd case-studies/international-roaming
    python3 web/build_data.py

Reads the Power BI export tables and writes web/data.json — the only file
index.html fetches at runtime, and the only file that ever needs to change
after a notebook re-run.

Data contract, in brief (see web/README.md for the full version):

  portfolio   full 13-point price grid, "as fitted" and "joint sensitivity"
              cases, unconditioned on macro scenario (macro_shift = 0). This
              is what the tool calls the "Base" economic condition.
  scenarios   Expansion / Contraction only, each at exactly the three prices
              the macro simulation was run at (1.00x / 1.15x / 1.20x), always
              under the "joint sensitivity" case — that's the only case the
              macro simulation covers, so there is no "as fitted" curve to
              show once a non-Base scenario is selected. The 1.15x point is
              a fixed stress-test price (the joint-sensitivity case's
              revenue-maximizing price, STRESS_TEST_PRICE below) — it is NOT
              tied to meta.recommended_price, which is read from the
              as-fitted case and currently sits at the 1.20x cap. The two
              happen to coincide when the recommendation is 1.15x, but must
              not be assumed equal: fact_macro_scenario only has rows at
              1.00/1.15/1.20, so if recommended_price is ever something else
              (as it is now, at 1.20x), scenario_prices would otherwise
              collide or miss a grid point. fact_macro_scenario also
              contains a "Base" row at those same three prices, from a
              separate (300-iteration) run of the same unconditioned case;
              it is deliberately NOT surfaced in the UI as a second "Base"
              source — see README — but is checked below for consistency
              with `portfolio` so a large divergence fails the build.
  segments    non-dormant segments, full 13-point grid, revenue AND expected
              purchasers. Both are deterministic expected-value decomposi-
              tions (not simulated), always under "joint sensitivity" +
              unconditioned macro — i.e. they correspond to the same
              condition as portfolio["joint sensitivity"], not to whichever
              scenario/case is selected in the UI. Purchasers = per-account
              P(at least one purchase) = 1 - prod(p_null over that account's
              forward trips), summed within segment; assumes conditional
              independence of an account's trip-purchase events. No
              interval — see the tool's Methodology section.
  purchasers  Now simulated (not just segment-level): portfolio (both
              cases, full grid) and Expansion/Contraction (3 prices) carry
              purchasers_p5/_median/_p95 from the same simulate() draws as
              revenue — added to the notebook's inner loop as a per-
              iteration count of distinct accounts with >=1 non-null trip
              (np.bincount over account_id), paired with revenue rather
              than a second independent simulation. eligible_accounts is
              the forward-panel population those counts are drawn from
              (N_ACCOUNTS_PANEL), constant across every row.
              Expansion/Contraction additionally carry a genuinely paired
              revenue/purchaser difference (1.15x vs 1.00x, same iterations)
              under `paired_at_stress_price` — preferred over subtracting
              marginal medians per the tool's spec (§12), and used by the
              page whenever the scenario and selected price make it valid.
              Named for the fixed 1.15x stress-test price, not for whichever
              price is currently recommended (see `scenarios` above).
              Segment-level purchasers remain the Track-A deterministic
              figure above; no plan to simulate intervals at that grain
              (see the scoping note in README's git history).
  probCurve   Population-mean P(null)/P(partial)/P(full) by price and case —
              the State Model's price-response mechanism itself, not a
              simulated quantity. Not conditioned on macro scenario: the
              macro shift only ever affects trip occurrence, never these
              state probabilities, so this curve is the same regardless of
              which economic scenario is selected in the UI.
  sensitivityGrid
              Independent response_scale x depth_scale controls, replacing
              the old bundled "Behavior Case" toggle. 3 points each
              (1.0, midpoint, the diagnostic-derived ceiling), full price
              grid, Base economy only — Expansion/Contraction stay fixed at
              the ceiling point (RESPONSE_SCALE_GRID[-1] /
              DEPTH_SCALE_GRID[-1] in the notebook), unchanged from before
              this grid existed. `cells["<ri>_<di>"]` indexes into
              `responseScale[ri]` x `depthScale[di]`. Purely additive at the
              notebook/export layer — the original two-case sweep
              (`portfolio`, `dim_model_case`, `fact_portfolio_simulation`)
              is untouched, so nothing depending on it needed to change.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent  # international-roaming/
PBI = BASE / "data" / "powerbi"
SYN = BASE / "data" / "synthetic"
OUT = Path(__file__).resolve().parent / "data.json"  # web/data.json

# Must match the notebook's Section 5.1 assumption exactly (same constant,
# duplicated here only for display metadata — the actual scaled figures are
# read from market_sizing.parquet, not recomputed).
MARKET_SHARE = 0.30

MACRO_CONSISTENCY_TOLERANCE = 0.05  # 5% — "Base" cross-check, see module docstring


def main():
    dim_price = pd.read_parquet(PBI / "dim_price.parquet")
    dim_segment = pd.read_parquet(PBI / "dim_segment.parquet")
    dim_model_case = pd.read_parquet(PBI / "dim_model_case.parquet")
    dim_assumption = pd.read_parquet(PBI / "dim_assumption.parquet")
    fact_portfolio = pd.read_parquet(PBI / "fact_portfolio_simulation.parquet")
    fact_macro = pd.read_parquet(PBI / "fact_macro_scenario.parquet")
    fact_seg_rev = pd.read_parquet(PBI / "fact_segment_revenue.parquet")
    fact_prob_curve = pd.read_parquet(PBI / "fact_probability_curve.parquet")
    fact_sensitivity = pd.read_parquet(PBI / "fact_sensitivity_grid.parquet")

    run_ids = set(
        pd.concat([
            dim_price["run_id"], dim_segment["run_id"], dim_model_case["run_id"],
            fact_portfolio["run_id"], fact_macro["run_id"], fact_seg_rev["run_id"],
            fact_prob_curve["run_id"], fact_sensitivity["run_id"],
        ]).unique()
    )
    assert len(run_ids) == 1, f"export tables span multiple run_ids: {run_ids}"
    run_id = run_ids.pop()

    grid = sorted(dim_price["price_multiplier"].round(4).unique().tolist())
    recommended_price = float(
        dim_price.loc[dim_price["is_recommended"], "price_multiplier"].iloc[0]
    )
    current_price = 1.0
    assert any(abs(g - current_price) < 1e-9 for g in grid), "1.00x missing from price grid"
    assert any(abs(g - recommended_price) < 1e-9 for g in grid), "recommended price missing from grid"

    # eligible_accounts is a single constant (the forward-panel population);
    # confirm it really is constant before treating it as a scalar downstream.
    assert fact_portfolio["eligible_accounts"].nunique() == 1, (
        "eligible_accounts is not constant in fact_portfolio_simulation"
    )
    assert fact_macro["eligible_accounts"].nunique() == 1, (
        "eligible_accounts is not constant in fact_macro_scenario"
    )
    eligible_accounts = int(fact_portfolio["eligible_accounts"].iloc[0])
    assert eligible_accounts == int(fact_macro["eligible_accounts"].iloc[0]), (
        "eligible_accounts differs between fact_portfolio_simulation and fact_macro_scenario"
    )

    # ---- portfolio: full grid, both cases, unconditioned (= "Base") ----
    portfolio = {}
    for case in ["as fitted", "joint sensitivity"]:
        d = fact_portfolio[fact_portfolio["case"] == case].sort_values("price_multiplier")
        assert d["price_multiplier"].round(4).tolist() == grid, f"{case}: price grid mismatch"
        assert (d["p5"] <= d["median"]).all() and (d["median"] <= d["p95"]).all(), f"{case}: p5<=median<=p95 violated"
        assert (d["p5"] >= 0).all(), f"{case}: negative revenue bound"
        assert (d["purchasers_p5"] <= d["purchasers_median"]).all() and (
            d["purchasers_median"] <= d["purchasers_p95"]
        ).all(), f"{case}: purchasers p5<=median<=p95 violated"
        assert (d["purchasers_p5"] >= 0).all(), f"{case}: negative purchasers bound"
        assert (d["purchasers_p95"] <= eligible_accounts + 1e-6).all(), (
            f"{case}: purchasers p95 exceeds eligible_accounts"
        )
        portfolio[case] = {
            "revenue_p5": d["p5"].round(0).astype(int).tolist(),
            "revenue_median": d["median"].round(0).astype(int).tolist(),
            "revenue_p95": d["p95"].round(0).astype(int).tolist(),
            "purchasers_p5": d["purchasers_p5"].round(0).astype(int).tolist(),
            "purchasers_median": d["purchasers_median"].round(0).astype(int).tolist(),
            "purchasers_p95": d["purchasers_p95"].round(0).astype(int).tolist(),
        }

    # ---- scenarios: Expansion / Contraction, 3 prices, joint sensitivity only ----
    # STRESS_TEST_PRICE is the joint-sensitivity case's revenue-maximizing price —
    # the fixed price the notebook's macro-scenario cell was run at (1.00/1.15/1.20
    # literally, independent of Model 04's RECOMMENDED_PRICE). Deliberately NOT
    # `recommended_price`: that's read from the as-fitted case and can land
    # anywhere on the grid (currently 1.20x, the cap) without a matching row in
    # fact_macro_scenario. See the `scenarios` entry in the module docstring.
    STRESS_TEST_PRICE = 1.15
    assert any(abs(g - STRESS_TEST_PRICE) < 1e-9 for g in grid), (
        "stress-test price missing from price grid"
    )
    scenario_prices = [1.0, STRESS_TEST_PRICE, 1.2]
    scenarios = {}
    for key, parquet_scenario in [("expansion", "Expansion"), ("contraction", "Contraction")]:
        d = fact_macro[fact_macro["scenario"] == parquet_scenario].sort_values("price")
        prices = d["price"].round(4).tolist()
        assert prices == [round(p, 4) for p in scenario_prices], (
            f"{key}: expected prices {scenario_prices}, got {prices}"
        )
        assert (d["p5"] <= d["median"]).all() and (d["median"] <= d["p95"]).all(), f"{key}: p5<=median<=p95 violated"
        assert (d["purchasers_p5"] <= d["purchasers_median"]).all() and (
            d["purchasers_median"] <= d["purchasers_p95"]
        ).all(), f"{key}: purchasers p5<=median<=p95 violated"
        assert (d["purchasers_p5"] >= 0).all(), f"{key}: negative purchasers bound"
        assert (d["purchasers_p95"] <= eligible_accounts + 1e-6).all(), (
            f"{key}: purchasers p95 exceeds eligible_accounts"
        )

        # Genuinely paired revenue/purchaser difference at the fixed stress-test
        # price (1.15x vs 1.00x, same simulation draws) — only defined there,
        # since that's the only pair the notebook's paired-difference cell
        # computes. Not the recommended price (see STRESS_TEST_PRICE above).
        stress_row = d.loc[d["price"].round(4) == round(STRESS_TEST_PRICE, 4)].iloc[0]
        assert pd.notna(stress_row["purchasers_paired_median"]), (
            f"{key}: missing paired purchaser difference at the stress-test price"
        )
        paired_at_stress_price = {
            "price": STRESS_TEST_PRICE,
            "revenue_paired_p5": round(float(stress_row["paired_p5"]), 0),
            "revenue_paired_median": round(float(stress_row["paired_median"]), 0),
            "revenue_paired_p95": round(float(stress_row["paired_p95"]), 0),
            "purchasers_paired_p5": round(float(stress_row["purchasers_paired_p5"]), 1),
            "purchasers_paired_median": round(float(stress_row["purchasers_paired_median"]), 1),
            "purchasers_paired_p95": round(float(stress_row["purchasers_paired_p95"]), 1),
        }

        scenarios[key] = {
            "price": prices,
            "revenue_p5": d["p5"].round(0).astype(int).tolist(),
            "revenue_median": d["median"].round(0).astype(int).tolist(),
            "revenue_p95": d["p95"].round(0).astype(int).tolist(),
            "purchasers_p5": d["purchasers_p5"].round(0).astype(int).tolist(),
            "purchasers_median": d["purchasers_median"].round(0).astype(int).tolist(),
            "purchasers_p95": d["purchasers_p95"].round(0).astype(int).tolist(),
            "paired_at_stress_price": paired_at_stress_price,
        }

    # Base-row consistency check: fact_macro_scenario's own "Base" row (separate,
    # 300-iteration run) should roughly agree with `portfolio["joint sensitivity"]`
    # at the same three prices. This isn't surfaced in the UI (see docstring) but a
    # large drift here means the two simulations have come apart and needs a look.
    macro_base = fact_macro[fact_macro["scenario"] == "Base"].sort_values("price")
    ref_df = fact_portfolio[fact_portfolio["case"] == "joint sensitivity"].copy()
    ref = ref_df.set_index(ref_df["price_multiplier"].round(4))["median"]
    for _, row in macro_base.iterrows():
        p = round(float(row["price"]), 4)
        if p in ref.index:
            drift = abs(row["median"] - ref[p]) / ref[p]
            assert drift < MACRO_CONSISTENCY_TOLERANCE, (
                f"Base macro-scenario row at {p}x drifted {drift:.1%} from the "
                f"unconditioned joint-sensitivity median — check the notebook rerun"
            )

    # ---- segments: non-dormant, full grid, revenue only (deterministic) ----
    dim_seg_active = dim_segment[~dim_segment["is_dormant"]].sort_values("sort_order")
    seg_order = dim_seg_active["segment_id"].astype(str).tolist()

    seg_curve = {}
    for _, seg_row in dim_seg_active.iterrows():
        sid = str(seg_row["segment_id"])
        d = fact_seg_rev[fact_seg_rev["segment"] == seg_row["segment"]].sort_values("price_multiplier")
        assert d["price_multiplier"].round(4).tolist() == grid, f"segment {sid}: price grid mismatch"
        assert (d["revenue"] >= 0).all(), f"segment {sid}: negative revenue"
        assert (d["purchasers"] >= 0).all(), f"segment {sid}: negative purchasers"
        assert (d["purchasers"] <= seg_row["accounts"] + 1e-6).all(), (
            f"segment {sid}: expected purchasers exceed account count"
        )
        seg_curve[sid] = {
            "revenue": d["revenue"].round(0).astype(int).tolist(),
            "purchasers": d["purchasers"].round(1).tolist(),
        }

    seg_meta = {}
    for _, r in dim_seg_active.iterrows():
        sid = str(r["segment_id"])
        seg_meta[sid] = {
            "name": r["segment"],
            "headline": r["headline"],
            "description": r["description"] if pd.notna(r["description"]) else "",
            "accounts": int(r["accounts"]),
            "acct_share": round(float(r["acct_share"]), 4),
            "rev_share": round(float(r["rev_share"]), 4),
            "business": round(float(r["business"]), 4),
            "rev_per_acct": round(float(r["rev_per_acct"]), 2),
        }

    # ---- dormant segment: disclosed, excluded from pricing comparisons ----
    dormant_rows = dim_segment[dim_segment["is_dormant"]]
    dormant = None
    if len(dormant_rows):
        r = dormant_rows.iloc[0]
        dormant = {
            "name": r["segment"],
            "accounts": int(r["accounts"]),
            "acct_share": round(float(r["acct_share"]), 4),
            "rev_share": round(float(r["rev_share"]), 4),
            "rev_per_acct": round(float(r["rev_per_acct"]), 2),
        }

    # ---- coverage-state probability curve: full grid, response-scale only ----
    # Not conditioned on economic scenario (macro shift never touches these) or
    # depth_scale (which only touches revenue magnitude, never coverage-state
    # probability). Indexed 0/1/2 to match sensitivityGrid.responseScale below.
    prob_curve_response_grid = sorted(fact_prob_curve["response_scale"].unique().tolist())
    assert len(prob_curve_response_grid) == 3, "expected a 3-point response_scale grid in prob curve"
    prob_curve = {}
    for ri, rs in enumerate(prob_curve_response_grid):
        d = fact_prob_curve[np.isclose(fact_prob_curve["response_scale"], rs)].sort_values("price_multiplier")
        assert d["price_multiplier"].round(4).tolist() == grid, f"prob curve [{ri}]: price grid mismatch"
        totals = d["p_null"] + d["p_partial"] + d["p_full"]
        assert np.allclose(totals, 1.0, atol=1e-6), f"prob curve [{ri}]: probabilities don't sum to 1"
        assert ((d[["p_null", "p_partial", "p_full"]] >= 0).all()).all(), f"prob curve [{ri}]: negative probability"
        prob_curve[str(ri)] = {
            "p_null": d["p_null"].round(4).tolist(),
            "p_partial": d["p_partial"].round(4).tolist(),
            "p_full": d["p_full"].round(4).tolist(),
        }

    # ---- sensitivity grid: independent response-scale x depth-scale controls ----
    # Base economy only (Expansion/Contraction stay fixed at the ceiling point,
    # unchanged — see build note in the notebook's "Sweep Sensitivity Grid" cell).
    response_scale_grid = sorted(fact_sensitivity["response_scale"].unique().tolist())
    depth_scale_grid = sorted(fact_sensitivity["depth_scale"].unique().tolist())
    assert len(response_scale_grid) == 3, "expected a 3-point response_scale grid"
    assert len(depth_scale_grid) == 3, "expected a 3-point depth_scale grid"
    assert abs(response_scale_grid[0] - 1.0) < 1e-6, "response_scale grid should start at 1.0"
    assert abs(depth_scale_grid[0] - 1.0) < 1e-6, "depth_scale grid should start at 1.0"

    sensitivity_cells = {}
    for ri, rs in enumerate(response_scale_grid):
        for di, ds in enumerate(depth_scale_grid):
            d = fact_sensitivity[
                np.isclose(fact_sensitivity["response_scale"], rs)
                & np.isclose(fact_sensitivity["depth_scale"], ds)
            ].sort_values("price_multiplier")
            assert d["price_multiplier"].round(4).tolist() == grid, (
                f"sensitivity grid [{ri},{di}]: price grid mismatch"
            )
            assert (d["p5"] <= d["median"]).all() and (d["median"] <= d["p95"]).all(), (
                f"sensitivity grid [{ri},{di}]: revenue p5<=median<=p95 violated"
            )
            assert (d["purchasers_p5"] <= d["purchasers_median"]).all() and (
                d["purchasers_median"] <= d["purchasers_p95"]
            ).all(), f"sensitivity grid [{ri},{di}]: purchasers p5<=median<=p95 violated"
            assert (d["p5"] >= 0).all() and (d["purchasers_p5"] >= 0).all(), (
                f"sensitivity grid [{ri},{di}]: negative value"
            )
            sensitivity_cells[f"{ri}_{di}"] = {
                "revenue_p5": d["p5"].round(0).astype(int).tolist(),
                "revenue_median": d["median"].round(0).astype(int).tolist(),
                "revenue_p95": d["p95"].round(0).astype(int).tolist(),
                "purchasers_p5": d["purchasers_p5"].round(0).astype(int).tolist(),
                "purchasers_median": d["purchasers_median"].round(0).astype(int).tolist(),
                "purchasers_p95": d["purchasers_p95"].round(0).astype(int).tolist(),
            }

    sensitivity_grid_payload = {
        "responseScale": [round(v, 4) for v in response_scale_grid],
        "depthScale": [round(v, 4) for v in depth_scale_grid],
        "cells": sensitivity_cells,
    }

    assert [round(v, 4) for v in prob_curve_response_grid] == [round(v, 4) for v in response_scale_grid], (
        "probability-curve response_scale grid disagrees with the sensitivity grid's"
    )

    # ---- segment/portfolio reconciliation note ----
    # Segment revenue is a deterministic expected-value decomposition; the portfolio
    # figure above is the median of a simulated (right-skewed) distribution. The two
    # are different estimands and will not sum to the same number — report the gap
    # rather than imply they reconcile.
    seg_sum_at_base = sum(
        fact_seg_rev.loc[
            (fact_seg_rev["segment"] == seg_row["segment"])
            & (fact_seg_rev["price_multiplier"].round(4) == current_price),
            "revenue",
        ].iloc[0]
        for _, seg_row in dim_seg_active.iterrows()
    )
    portfolio_median_at_base = portfolio["joint sensitivity"]["revenue_median"][grid.index(current_price)]
    reconciliation_gap_pct = round(
        (seg_sum_at_base / portfolio_median_at_base - 1) * 100, 1
    )

    assumption_values = dim_assumption.set_index("assumption")["value"]

    # ---- market sizing: I-92 real-world travel anchor x assumed carrier share ----
    # Reads the notebook's Section 5.1 output (market_sizing.parquet) rather than
    # recomputing it, so the tool and the notebook/deck always agree by construction.
    market_sizing_df = pd.read_parquet(SYN / "market_sizing.parquet")
    market_sizing_payload = {
        str(round(float(row["Price Multiplier"]), 4)): {
            "revenue_per_trip": round(float(row["Revenue per Trip (As Fitted)"]), 2),
            "scaled_annual_revenue": round(float(row["Scaled Annual Revenue"]), 0),
            "scaled_lift": round(float(row["Scaled Lift vs. Standard"]), 0),
            "share_of_target": round(float(row["Share of $100M Target"]), 4),
        }
        for _, row in market_sizing_df.iterrows()
    }
    i92 = pd.read_csv(BASE / "data" / "reference" / "us_i92_air_travel.csv")
    i92_annual = (
        i92.loc[~i92["Year"].isin([2020, 2021, 2026])]
        .groupby("Year")["U.S. Citizen Originating"]
        .sum()
    )
    i92_year = int(i92_annual.index.max())
    i92_trips = float(i92_annual.loc[i92_year])

    payload = {
        "meta": {
            "run_id": run_id,
            "current_price": current_price,
            "recommended_price": recommended_price,
            "purchasers_available": True,
            "segment_purchasers_available": True,
            "eligible_accounts": eligible_accounts,
            "response_scale_joint_sensitivity": round(
                float(assumption_values.get("response scale (joint sensitivity)")), 4
            ),
            "depth_scale_joint_sensitivity": round(
                float(assumption_values.get("depth scale (joint sensitivity)")), 4
            ),
            "reconciliation_gap_pct": reconciliation_gap_pct,
        },
        "grid": [round(g, 4) for g in grid],
        "portfolio": portfolio,
        "scenarios": scenarios,
        "segOrder": seg_order,
        "segMeta": seg_meta,
        "segCurve": seg_curve,
        "dormant": dormant,
        "probCurve": prob_curve,
        "sensitivityGrid": sensitivity_grid_payload,
        "marketSizing": {
            "meta": {
                "i92_year": i92_year,
                "i92_trips": round(i92_trips, 0),
                "market_share": MARKET_SHARE,
                "national_trips": round(i92_trips * MARKET_SHARE, 0),
                "target": 100_000_000,
            },
            "byPrice": market_sizing_payload,
        },
    }

    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
