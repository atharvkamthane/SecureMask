"""E4: Correlation analysis between Human Risk Perception and PEI Scores.

Loads human ratings from E4_Human_Rating_Sheet.csv (mean per scenario) and
calculated PEI scores from e4_pei_scores.json, then calculates Pearson r,
Spearman rho, associated p-values, and 95% bootstrap confidence intervals.

Uses exclusively the actual N=3 human rater data.

Usage::
    python -m securemask.eval.calculate_e4_correlation [--csv <path>] [--json <path>]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import pearsonr, spearmanr


def load_human_ratings(csv_path: Path) -> dict[str, float]:
    """Load human rating sheet CSV and compute mean score per scenario_id."""
    scores_by_scenario: dict[str, list[float]] = defaultdict(list)

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            scenario_id = row.get("Scenario_ID", "").strip()
            raw_score = row.get("Perceived_Privacy_Risk_Score_1_to_10", "").strip()
            if scenario_id and raw_score:
                try:
                    scores_by_scenario[scenario_id].append(float(raw_score))
                except ValueError:
                    pass

    means: dict[str, float] = {}
    for sc_id, scores in scores_by_scenario.items():
        means[sc_id] = sum(scores) / len(scores)

    return means


def load_pei_scores(json_path: Path) -> dict[str, float]:
    """Load PEI scores from e4_pei_scores.json."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return {entry["scenario_id"]: float(entry["pei_score"]) for entry in data}


def compute_bootstrap_ci(
    x: list[float],
    y: list[float],
    n_bootstraps: int = 2000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Compute 95% bootstrap confidence intervals for Pearson r and Spearman rho."""
    rng = np.random.RandomState(seed)
    n = len(x)
    r_boots: list[float] = []
    rho_boots: list[float] = []

    for _ in range(n_bootstraps):
        idx = rng.choice(n, size=n, replace=True)
        xb = [x[i] for i in idx]
        yb = [y[i] for i in idx]
        if len(set(xb)) <= 1 or len(set(yb)) <= 1:
            continue
        try:
            rb, _ = pearsonr(xb, yb)
            rhob, _ = spearmanr(xb, yb)
            if not np.isnan(rb) and not np.isnan(rhob):
                r_boots.append(float(rb))
                rho_boots.append(float(rhob))
        except Exception:
            continue

    r_low, r_high = np.percentile(r_boots, [100 * (alpha / 2), 100 * (1 - alpha / 2)])
    rho_low, rho_high = np.percentile(rho_boots, [100 * (alpha / 2), 100 * (1 - alpha / 2)])
    return (float(r_low), float(r_high)), (float(rho_low), float(rho_high))


def main(argv: list[str] | None = None) -> None:
    eval_dir = Path(__file__).resolve().parent
    default_csv = eval_dir / "E4_Human_Rating_Sheet.csv"
    default_json = eval_dir / "e4_pei_scores.json"

    parser = argparse.ArgumentParser(description="Calculate E4 Pearson r and Spearman rho correlation.")
    parser.add_argument("--csv", type=Path, default=default_csv, help="Path to E4_Human_Rating_Sheet.csv")
    parser.add_argument("--json", type=Path, default=default_json, help="Path to e4_pei_scores.json")
    args = parser.parse_args(argv)

    if not args.csv.exists():
        print(f"Error: Human rating sheet CSV not found at {args.csv}")
        return

    if not args.json.exists():
        print(f"Error: PEI scores JSON not found at {args.json}. Run run_e4_pei_scores first.")
        return

    human_means = load_human_ratings(args.csv)
    pei_scores = load_pei_scores(args.json)

    # Order by Scenario 1 to 12
    scenario_order = [f"Scenario {i}" for i in range(1, 13)]

    human_vec: list[float] = []
    pei_vec: list[float] = []
    valid_scenarios: list[str] = []

    print(f"\nScenario Data Comparison:")
    print(f"{'Scenario':<14} {'Mean Human Rating (1-10)':>25} {'Calculated PEI Score':>22}")
    print("-" * 65)

    for sc_id in scenario_order:
        if sc_id in human_means and sc_id in pei_scores:
            h_val = human_means[sc_id]
            p_val = pei_scores[sc_id]
            human_vec.append(h_val)
            pei_vec.append(p_val)
            valid_scenarios.append(sc_id)
            print(f"{sc_id:<14} {h_val:>25.2f} {p_val:>22.1f}")
        else:
            print(f"Warning: Missing data for {sc_id}")

    if len(human_vec) < 3:
        print("Error: Need at least 3 matching scenarios to calculate correlation.")
        return

    r, p_val_r = pearsonr(human_vec, pei_vec)
    rho, p_val_rho = spearmanr(human_vec, pei_vec)
    (r_ci_low, r_ci_high), (rho_ci_low, rho_ci_high) = compute_bootstrap_ci(human_vec, pei_vec)

    print("-" * 65)
    print("\nE4 Pilot Human-Validation Correlation Results (N=3 Real Raters):")
    print("=" * 65)
    print(f"Pearson correlation (r):    {r:.4f}  (95% CI: [{r_ci_low:.4f}, {r_ci_high:.4f}])")
    print(f"Pearson p-value:            {p_val_r:.4e}")
    print(f"Spearman correlation (rho): {rho:.4f}  (95% CI: [{rho_ci_low:.4f}, {rho_ci_high:.4f}])")
    print(f"Spearman p-value:          {p_val_rho:.4e}")
    print("=" * 65)


if __name__ == "__main__":
    main()
