"""E4: Correlation analysis between Human Risk Perception and PEI Scores.

Loads human ratings from E4_Human_Rating_Sheet.csv (mean per scenario) and
calculated PEI scores from e4_pei_scores.json, then calculates Pearson r,
Spearman rho, and their associated p-values.

Usage::
    python -m securemask.eval.calculate_e4_correlation [--csv <path>] [--json <path>]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

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

    print("-" * 65)
    print("\nE4 Correlation Results:")
    print("=" * 45)
    print(f"Pearson correlation (r):    {r:.4f}")
    print(f"Pearson p-value:            {p_val_r:.4e}")
    print(f"Spearman correlation (rho): {rho:.4f}")
    print(f"Spearman p-value:          {p_val_rho:.4e}")
    print("=" * 45)


if __name__ == "__main__":
    main()
