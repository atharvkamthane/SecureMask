"""E4: Sensitivity analysis for residual identifier attenuation parameter (lambda).

Evaluates the stability of Privacy Exposure Index (PEI) rankings and human risk
perception correlations across different lambda values:
    lambda in [0.25, 0.50, 0.75, 1.00]

Uses exclusively real N=3 human rater data from securemask/eval/E4_Human_Rating_Sheet.csv.

Usage::
    python -m securemask.eval.run_lambda_sensitivity
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from scipy.stats import pearsonr, spearmanr

from securemask.eval.calculate_e4_correlation import load_human_ratings
from securemask.eval.run_e4_pei_scores import run_e4_pei_calculation


def run_sensitivity_analysis(
    lambda_values: list[float] | None = None,
    csv_path: Path | None = None,
) -> dict[str, Any]:
    if lambda_values is None:
        lambda_values = [0.25, 0.50, 0.75, 1.00]

    eval_dir = Path(__file__).resolve().parent
    if csv_path is None:
        csv_path = eval_dir / "E4_Human_Rating_Sheet.csv"

    human_means = load_human_ratings(csv_path)
    scenario_order = [f"Scenario {i}" for i in range(1, 13)]
    human_vec = [human_means[sc] for sc in scenario_order]

    results_by_lambda: dict[float, dict[str, Any]] = {}
    rankings_by_lambda: dict[float, list[str]] = {}

    for lam in lambda_values:
        scenario_results = run_e4_pei_calculation(lambda_param=lam)
        pei_dict = {r["scenario_id"]: r["pei_score"] for r in scenario_results}
        pei_vec = [pei_dict[sc] for sc in scenario_order]

        r, p_val_r = pearsonr(human_vec, pei_vec)
        rho, p_val_rho = spearmanr(human_vec, pei_vec)

        # Rank scenarios by PEI score ascending (ties preserve order)
        sorted_scenarios = sorted(scenario_order, key=lambda sc: pei_dict[sc])
        rankings_by_lambda[lam] = sorted_scenarios

        results_by_lambda[lam] = {
            "lambda": lam,
            "pei_dict": pei_dict,
            "pei_vec": pei_vec,
            "pearson_r": r,
            "pearson_p": p_val_r,
            "spearman_rho": rho,
            "spearman_p": p_val_rho,
            "ranking": sorted_scenarios,
        }

    # Check if scenario ranking is invariant across all tested lambda values
    base_ranking = rankings_by_lambda[lambda_values[0]]
    ranking_invariant = all(
        rankings_by_lambda[lam] == base_ranking for lam in lambda_values[1:]
    )

    return {
        "lambda_values": lambda_values,
        "human_means": human_means,
        "results_by_lambda": results_by_lambda,
        "ranking_invariant": ranking_invariant,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="PEI lambda sensitivity analysis.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parent / "E4_Human_Rating_Sheet.csv",
        help="Path to E4_Human_Rating_Sheet.csv (N=3 real raters)",
    )
    args = parser.parse_args()

    lambdas = [0.25, 0.50, 0.75, 1.00]
    report = run_sensitivity_analysis(lambda_values=lambdas, csv_path=args.csv)

    print("=" * 90)
    print("SECUREMASK PEI SENSITIVITY ANALYSIS: RESIDUAL IDENTIFIER ATTENUATION (lambda)")
    print(f"Dataset: N=3 Real Human Raters ({args.csv.name})")
    print("=" * 90)

    # Table 1: Scenario PEI values across lambdas
    header = f"{'Scenario ID':<14} {'Human Mean':>12}" + "".join(
        f"{f'lambda={lam:.2f}':>15}" for lam in lambdas
    )
    print(header)
    print("-" * len(header))

    scenario_order = [f"Scenario {i}" for i in range(1, 13)]
    for sc in scenario_order:
        h_val = report["human_means"][sc]
        row_str = f"{sc:<14} {h_val:>12.2f}"
        for lam in lambdas:
            pei_val = report["results_by_lambda"][lam]["pei_dict"][sc]
            row_str += f"{pei_val:>15.1f}"
        print(row_str)

    print("-" * len(header))

    # Table 2: Correlation metrics
    print("\nCorrelation Summary Across Policy Parameter Values:")
    print("=" * 70)
    print(f"{'lambda':<10} {'Pearson r':>12} {'p-value':>14} {'Spearman rho':>14} {'p-value':>14}")
    print("-" * 70)
    for lam in lambdas:
        res = report["results_by_lambda"][lam]
        print(
            f"{lam:<10.2f} {res['pearson_r']:>12.4f} {res['pearson_p']:>14.4e} "
            f"{res['spearman_rho']:>14.4f} {res['spearman_p']:>14.4e}"
        )
    print("=" * 70)

    print(f"\nScenario Ranking Invariant Across All lambda: {report['ranking_invariant']}")
    if report["ranking_invariant"]:
        print("Conclusion: Relative scenario ranking is completely stable under lambda in [0.25, 1.00].")
    else:
        print("Note: Scenario ranking varies across lambda.")


if __name__ == "__main__":
    main()
