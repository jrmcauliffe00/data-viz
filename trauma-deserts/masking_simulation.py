"""What a cross-section of firearm deaths can and cannot separate.

Observed deaths mix two unmeasured pieces: how often people are shot, and
whether a longer trip makes those shootings more often fatal. A behavioral
response (more shootings where a rescue is close) and a survival effect
(fewer deaths where a rescue is close) push the death rate in opposite
directions. This script fits the regression the file identifies, then keeps
the Monte Carlo draws whose death rates still match that regression.

Run from trauma-deserts/ so ../data resolves.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "trauma-deserts" / "county_distance.csv"
OUT = ROOT

# Assumptions, not estimates. The county file has no intent split and no
# count of people who were shot and lived.
SUICIDE_SHARE = 0.55
FATALITY_AT_MEAN = 0.25
FATALITY_FLOOR = 0.05
FATALITY_CAP = 0.90
RNG_SEED = 14
N_DRAWS = 4000


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.average(values, weights=weights))


def wls_beta(y: np.ndarray, x: np.ndarray, weights: np.ndarray) -> np.ndarray:
    sw = np.sqrt(weights)
    design = np.column_stack([np.ones(len(y)), x])
    beta, *_ = np.linalg.lstsq(design * sw[:, None], y * sw, rcond=None)
    return beta


def fit_hc1(y: pd.Series, x: pd.DataFrame, weights: pd.Series | None = None):
    design = sm.add_constant(x)
    if weights is None:
        return sm.OLS(y, design).fit(cov_type="HC1")
    return sm.WLS(y, design, weights=weights).fit(cov_type="HC1")


def load_counties() -> pd.DataFrame:
    counties = pd.read_csv(DATA)
    published = counties.dropna(
        subset=["firearm_rate", "distance_miles", "log_density", "population"]
    ).copy()
    published = published[published["population"] > 0]
    for column in ["pct_black", "pct_hispanic", "pct_aian", "pct_asian", "pct_rural"]:
        published[column] = published[column].fillna(0.0)
    return published


def association_table(published: pd.DataFrame) -> dict:
    y = published["firearm_rate"]
    weights = published["population"]
    distance = fit_hc1(
        y,
        published[["distance_miles", "log_density"]],
        weights,
    )
    groups = {
        "log density and rural share": ["log_density", "pct_rural"],
        "race and Hispanic shares": ["pct_black", "pct_hispanic", "pct_aian", "pct_asian"],
        "distance": ["distance_miles"],
    }
    full_columns = [column for columns in groups.values() for column in columns]
    full = fit_hc1(y, published[full_columns], weights)
    drops = []
    for name, columns in groups.items():
        reduced_columns = [column for column in full_columns if column not in columns]
        reduced = fit_hc1(y, published[reduced_columns], weights)
        drops.append(
            {
                "group": name,
                "weighted_r2_without": float(reduced.rsquared),
                "r2_drop": float(full.rsquared - reduced.rsquared),
            }
        )
    contrasts = {
        "distance_miles": ("10 miles", 10.0),
        "log_density": ("tenfold density", 1.0),
        "pct_rural": ("10 points more rural", 10.0),
        "pct_black": ("10 points Non-Hispanic Black", 10.0),
        "pct_hispanic": ("10 points Hispanic", 10.0),
        "pct_aian": ("10 points American Indian or Alaska Native", 10.0),
        "pct_asian": ("10 points Asian", 10.0),
    }
    contrast_rows = []
    for column, (label, step) in contrasts.items():
        coef = float(full.params[column]) * step
        low, high = (full.conf_int().loc[column] * step).tolist()
        contrast_rows.append(
            {
                "contrast": label,
                "column": column,
                "associated_deaths_per_100k": coef,
                "ci_low": float(low),
                "ci_high": float(high),
                "p": float(full.pvalues[column]),
            }
        )
    return {
        "n": int(len(published)),
        "distance_per_10_miles": float(distance.params["distance_miles"] * 10),
        "distance_ci": [float(v) * 10 for v in distance.conf_int().loc["distance_miles"].tolist()],
        "distance_p": float(distance.pvalues["distance_miles"]),
        "density_model_r2": float(distance.rsquared),
        "full_weighted_r2": float(full.rsquared),
        "r2_drop": drops,
        "contrasts": contrast_rows,
        "full_model": full,
        "distance_model": distance,
    }


def simulate_rates(
    skeleton: np.ndarray,
    z: np.ndarray,
    phi: float,
    behavior: float,
    suicide_share: float = SUICIDE_SHARE,
    fatality_at_mean: float = FATALITY_AT_MEAN,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return simulated death rate, shooting incidence, and fatality.

    `behavior` is the log change in shooting incidence per 10 miles.
    Negative behavior means more shootings where the trip is shorter.
    """
    fatality = np.clip(fatality_at_mean + phi * z, FATALITY_FLOOR, FATALITY_CAP)
    shooting_deaths = (1.0 - suicide_share) * skeleton
    incidence_at_mean_fatality = shooting_deaths / fatality_at_mean
    incidence = incidence_at_mean_fatality * np.exp(np.clip(behavior * z, -3.0, 3.0))
    deaths = suicide_share * skeleton + incidence * fatality
    return deaths, incidence, fatality


def partial_distance_slope(
    deaths: np.ndarray, z: np.ndarray, log_density: np.ndarray, weights: np.ndarray
) -> float:
    beta = wls_beta(deaths, np.column_stack([z, log_density]), weights)
    return float(beta[1])


def monte_carlo(published: pd.DataFrame, ci: tuple[float, float]) -> dict:
    weights = published["population"].to_numpy()
    log_density = published["log_density"].to_numpy()
    miles = published["distance_miles"].to_numpy()
    rate = published["firearm_rate"].to_numpy()
    mean_miles = weighted_mean(miles, weights)
    z = (miles - mean_miles) / 10.0

    density_beta = wls_beta(rate, log_density, weights)
    skeleton = density_beta[0] + density_beta[1] * log_density
    residual_sd = float(np.sqrt(np.average((rate - skeleton) ** 2, weights=weights)))

    rng = np.random.default_rng(RNG_SEED)
    phi = rng.uniform(-0.02, 0.08, N_DRAWS)
    behavior = rng.uniform(-0.45, 0.15, N_DRAWS)
    kept = np.zeros(N_DRAWS, dtype=bool)
    slopes = np.zeros(N_DRAWS)
    for i in range(N_DRAWS):
        deaths, _, _ = simulate_rates(skeleton, z, float(phi[i]), float(behavior[i]))
        deaths = deaths + rng.normal(0.0, residual_sd, size=len(deaths))
        slopes[i] = partial_distance_slope(deaths, z, log_density, weights)
        kept[i] = ci[0] <= slopes[i] <= ci[1]

    return {
        "mean_miles": mean_miles,
        "residual_sd": residual_sd,
        "phi": phi,
        "behavior": behavior,
        "slopes": slopes,
        "kept": kept,
        "z": z,
        "skeleton": skeleton,
        "weights": weights,
        "log_density": log_density,
        "miles": miles,
    }


# phi is an assumed fatality change per 10 miles. behavior is the log change in
# shootings per 10 miles. The third pair is the one whose refit county slope
# lands inside the real interval; the local tangent -phi/F0 does not, once
# low-density counties also sit farther out.
SCENARIOS = [
    ("neither effect", 0.0, 0.0),
    ("survival only, behavior unchanged", 0.04, 0.0),
    ("survival offset by more shootings nearby", 0.04, -0.10),
]


def scenario_curves(mc: dict) -> list[dict]:
    """Three labeled points. The first and third match the county slope."""
    scenarios = SCENARIOS
    bins = [0, 5, 15, 30, 50, 80, 150, 10_000]
    labels = ["0–5", "5–15", "15–30", "30–50", "50–80", "80–150", "150+"]
    curves = []
    for name, phi, behavior in scenarios:
        deaths, incidence, fatality = simulate_rates(mc["skeleton"], mc["z"], phi, behavior)
        slope = partial_distance_slope(deaths, mc["z"], mc["log_density"], mc["weights"])
        bin_id = np.digitize(mc["miles"], bins) - 1
        rows = []
        for i, label in enumerate(labels):
            mask = bin_id == i
            if not mask.any():
                continue
            w = mc["weights"][mask]
            rows.append(
                {
                    "bin": label,
                    "people": float(w.sum()),
                    "deaths_per_100k": weighted_mean(deaths[mask], w),
                    "shootings_per_100k": weighted_mean(incidence[mask], w),
                    "fatality": weighted_mean(fatality[mask], w),
                    "miles": weighted_mean(mc["miles"][mask], w),
                }
            )
        curves.append(
            {
                "name": name,
                "phi": phi,
                "behavior": behavior,
                "partial_slope_per_10_miles": slope,
                "bins": rows,
            }
        )
    return curves


def real_bins(published: pd.DataFrame) -> list[dict]:
    bins = [0, 5, 15, 30, 50, 80, 150, 10_000]
    labels = ["0–5", "5–15", "15–30", "30–50", "50–80", "80–150", "150+"]
    bin_id = np.digitize(published["distance_miles"], bins) - 1
    rows = []
    for i, label in enumerate(labels):
        part = published[bin_id == i]
        if part.empty:
            continue
        rows.append(
            {
                "bin": label,
                "people": float(part["population"].sum()),
                "deaths_per_100k": weighted_mean(
                    part["firearm_rate"].to_numpy(), part["population"].to_numpy()
                ),
                "counties": int(len(part)),
            }
        )
    return rows


def residuals(published: pd.DataFrame) -> dict:
    columns = ["log_density", "pct_rural", "pct_black", "pct_hispanic", "pct_aian", "pct_asian"]
    reduced = fit_hc1(published["firearm_rate"], published[columns], published["population"])
    predicted = reduced.predict(sm.add_constant(published[columns]))
    frame = published.copy()
    frame["predicted"] = predicted
    frame["residual"] = frame["firearm_rate"] - frame["predicted"]
    mean_rate = weighted_mean(frame["firearm_rate"].to_numpy(), frame["population"].to_numpy())
    mean_miles = weighted_mean(frame["distance_miles"].to_numpy(), frame["population"].to_numpy())
    high_long = frame[(frame["firearm_rate"] > mean_rate) & (frame["distance_miles"] > mean_miles)]
    still = high_long[high_long["residual"] > 0]

    def summary(part: pd.DataFrame) -> dict:
        people = float(part["population"].sum())
        return {
            "counties": int(len(part)),
            "people": people,
            "aian_share": weighted_mean(part["pct_aian"].to_numpy(), part["population"].to_numpy()) / 100.0,
            "black_share": weighted_mean(part["pct_black"].to_numpy(), part["population"].to_numpy()) / 100.0,
            "white_share": weighted_mean(part["pct_white"].to_numpy(), part["population"].to_numpy()) / 100.0,
            "aian_counties_over_10pct": int((part["pct_aian"] >= 10).sum()),
            "people_in_aian_counties_over_10pct": float(part.loc[part["pct_aian"] >= 10, "population"].sum()),
        }

    still = still.copy()
    still["excess_deaths_per_year"] = still["residual"] * still["population"] / 1e5
    top = still.nlargest(12, "excess_deaths_per_year")[
        [
            "NAMELSAD",
            "STATE_NAME",
            "firearm_rate",
            "predicted",
            "residual",
            "distance_miles",
            "population",
            "excess_deaths_per_year",
            "pct_aian",
            "pct_black",
        ]
    ]
    records = []
    for row in top.itertuples(index=False):
        records.append(
            {
                "county": f"{row.NAMELSAD}, {row.STATE_NAME}",
                "firearm_rate": round(float(row.firearm_rate), 1),
                "predicted": round(float(row.predicted), 1),
                "residual": round(float(row.residual), 1),
                "miles": round(float(row.distance_miles), 0),
                "people": int(row.population),
                "excess_deaths_per_year": round(float(row.excess_deaths_per_year), 0),
                "pct_aian": round(float(row.pct_aian), 1),
                "pct_black": round(float(row.pct_black), 1),
            }
        )
    return {
        "mean_rate": mean_rate,
        "mean_miles": mean_miles,
        "high_long": summary(high_long),
        "still_high_after_model": summary(still),
        "top_residuals": records,
    }


def fixed_density_profile(mean_miles: float, mean_rate: float) -> list[dict]:
    """Deaths and shootings at the national mean rate, miles varying, density fixed."""
    suicide = SUICIDE_SHARE * mean_rate
    incidence_at_mean = (1.0 - SUICIDE_SHARE) * mean_rate / FATALITY_AT_MEAN
    miles = [5, 15, 23, 40, 60, 80]
    profiles = []
    for name, phi, behavior in SCENARIOS:
        rows = []
        for mile in miles:
            z = (mile - mean_miles) / 10.0
            fatality = float(np.clip(FATALITY_AT_MEAN + phi * z, FATALITY_FLOOR, FATALITY_CAP))
            incidence = float(incidence_at_mean * np.exp(np.clip(behavior * z, -3.0, 3.0)))
            deaths = float(suicide + incidence * fatality)
            rows.append(
                {
                    "miles": mile,
                    "deaths_per_100k": deaths,
                    "shootings_per_100k": incidence,
                    "fatality": fatality,
                }
            )
        profiles.append({"name": name, "phi": phi, "behavior": behavior, "rows": rows})
    return profiles


def plot_worlds(mc: dict, kept_share: float, ci: list[float]) -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#333333",
            "axes.labelcolor": "#1a1a1a",
            "xtick.color": "#333333",
            "ytick.color": "#333333",
            "text.color": "#1a1a1a",
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.5))

    ax = axes[0]
    phi = mc["phi"]
    behavior = mc["behavior"]
    kept = mc["kept"]
    ax.scatter(phi[~kept], behavior[~kept], s=8, c="#c8c8c8", linewidths=0, label="Rejected by the county slope", rasterized=True)
    ax.scatter(phi[kept], behavior[kept], s=10, c="#1f4b99", linewidths=0, label="Still matches the counties", rasterized=True)
    phi_line = np.linspace(-0.02, 0.08, 40)
    ax.plot(phi_line, -phi_line / FATALITY_AT_MEAN, color="#1a1a1a", lw=1.0, label="Exact offset at the mean")
    ax.scatter([0.0], [0.0], s=46, c="#1a1a1a", zorder=3)
    ax.scatter([0.04], [0.0], s=46, facecolors="none", edgecolors="#9a3b2f", linewidths=1.4, zorder=3)
    ax.scatter([0.04], [-0.10], s=46, c="#9a3b2f", zorder=3)
    ax.axhline(0, color="#888888", lw=0.6)
    ax.axvline(0, color="#888888", lw=0.6)
    ax.set_xlabel("Assumed fatality change per 10 miles")
    ax.set_ylabel("Assumed log change in shootings per 10 miles")
    ax.set_title("Worlds that fit the same death rates", loc="left", fontsize=11)
    ax.set_xlim(-0.025, 0.085)
    ax.set_ylim(-0.48, 0.18)

    ax = axes[1]
    profile = fixed_density_profile(mc["mean_miles"], 13.4)
    miles = [row["miles"] for row in profile[0]["rows"]]
    deaths_neither = [row["deaths_per_100k"] for row in profile[0]["rows"]]
    deaths_survival = [row["deaths_per_100k"] for row in profile[1]["rows"]]
    deaths_offset = [row["deaths_per_100k"] for row in profile[2]["rows"]]
    shootings_offset = [row["shootings_per_100k"] for row in profile[2]["rows"]]
    ax.plot(miles, deaths_neither, color="#1a1a1a", lw=1.6, label="Deaths, neither effect")
    ax.plot(miles, deaths_survival, color="#9a3b2f", ls=":", lw=1.5, label="Deaths, survival only (rejected)")
    ax.plot(miles, deaths_offset, color="#9a3b2f", lw=1.5, label="Deaths, offset world")
    ax.plot(miles, shootings_offset, color="#1f4b99", lw=1.6, label="Shootings, offset world")
    ax.set_xlabel("Miles, at the national death rate and a fixed density")
    ax.set_ylabel("Per 100,000 residents")
    ax.set_title("Same deaths, different shootings", loc="left", fontsize=11)
    ax.set_xlim(0, 85)

    handles, labels = [], []
    for axis in axes:
        h, lab = axis.get_legend_handles_labels()
        handles.extend(h)
        labels.extend(lab)
    fig.legend(
        handles,
        labels,
        frameon=False,
        fontsize=8,
        loc="lower center",
        ncol=3,
        bbox_to_anchor=(0.5, 0.10),
    )
    caption = textwrap.fill(
        "A draw is kept when its population-weighted distance slope, log density held fixed, "
        f"lands in {ci[0]:+.2f} to {ci[1]:+.2f} deaths per 100,000 per 10 miles. "
        "Black dot: neither effect. Open circle: fatality rises and shootings do not (rejected). "
        "Filled circle: the same fatality rise, with fewer shootings farther out (kept). "
        f"{kept_share:.0%} of {N_DRAWS:,} draws kept. "
        f"A suicide-like share of {SUICIDE_SHARE:.0%} and a fatality of {FATALITY_AT_MEAN:.2f} "
        f"at {mc['mean_miles']:.0f} miles are assumptions, not estimates.",
        width=150,
    )
    fig.text(0.01, 0.015, caption, fontsize=7.5, color="#4d4d4d", va="bottom")
    fig.tight_layout(rect=(0, 0.20, 1, 1))
    fig.savefig(OUT / "equivalent_worlds.png", dpi=160)
    plt.close(fig)


def plot_contributions(association: dict) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    rows = list(reversed(association["contrasts"]))
    y = np.arange(len(rows))
    coef = np.array([row["associated_deaths_per_100k"] for row in rows])
    low = np.array([row["ci_low"] for row in rows])
    high = np.array([row["ci_high"] for row in rows])
    colors = ["#1f4b99" if row["column"] == "distance_miles" else "#4d4d4d" for row in rows]
    ax.axvline(0, color="#888888", lw=0.7)
    ax.errorbar(coef, y, xerr=[coef - low, high - coef], fmt="none", ecolor="#b0b0b0", capsize=2)
    ax.scatter(coef, y, c=colors, s=28, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([row["contrast"] for row in rows])
    ax.set_xlabel("Associated firearm deaths per 100,000")
    ax.set_title("What lines up with the published rate", loc="left", fontsize=12)
    fig.text(
        0.01,
        0.01,
        "Population-weighted least squares, HC1 intervals. Counties with a published firearm rate. "
        "These are associations. They are not effects of changing a county.",
        fontsize=7.5,
        color="#4d4d4d",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "what_lines_up.png", dpi=160)
    plt.close(fig)


def main() -> None:
    published = load_counties()
    association = association_table(published)
    ci = (association["distance_ci"][0], association["distance_ci"][1])
    mc = monte_carlo(published, ci)
    curves = scenario_curves(mc)
    observed_bins = real_bins(published)
    leftover = residuals(published)
    kept_share = float(mc["kept"].mean())
    plot_worlds(mc, kept_share, list(ci))
    plot_contributions(association)
    profiles = fixed_density_profile(mc["mean_miles"], leftover["mean_rate"])

    # Downsample the cloud for the canvas. Keep every kept draw and a sample of rejects.
    rng = np.random.default_rng(7)
    reject_index = np.flatnonzero(~mc["kept"])
    keep_index = np.flatnonzero(mc["kept"])
    reject_sample = rng.choice(reject_index, size=min(350, len(reject_index)), replace=False)
    cloud = []
    for index in np.concatenate([keep_index, reject_sample]):
        cloud.append(
            {
                "phi": round(float(mc["phi"][index]), 4),
                "behavior": round(float(mc["behavior"][index]), 4),
                "slope": round(float(mc["slopes"][index]), 3),
                "kept": bool(mc["kept"][index]),
            }
        )

    payload = {
        "n_counties": association["n"],
        "distance_per_10_miles": association["distance_per_10_miles"],
        "distance_ci": association["distance_ci"],
        "distance_p": association["distance_p"],
        "density_model_r2": association["density_model_r2"],
        "full_weighted_r2": association["full_weighted_r2"],
        "r2_drop": association["r2_drop"],
        "contrasts": association["contrasts"],
        "assumptions": {
            "suicide_share": SUICIDE_SHARE,
            "fatality_at_mean": FATALITY_AT_MEAN,
            "mean_miles": mc["mean_miles"],
            "draws": N_DRAWS,
            "kept_share": kept_share,
            "kept_draws": int(mc["kept"].sum()),
        },
        "scenarios": [
            {
                "name": curve["name"],
                "phi": curve["phi"],
                "behavior": curve["behavior"],
                "partial_slope_per_10_miles": curve["partial_slope_per_10_miles"],
                "bins": curve["bins"],
            }
            for curve in curves
        ],
        "observed_bins": observed_bins,
        "profiles": profiles,
        "residuals": leftover,
        "cloud": cloud,
    }
    (OUT / "masking_results.json").write_text(json.dumps(payload, indent=2))
    low, high = association["distance_ci"]
    print(
        f"Density-adjusted slope {association['distance_per_10_miles']:+.2f} "
        f"deaths per 100,000 per 10 miles (95% CI {low:+.2f} to {high:+.2f}). "
        f"Kept {int(mc['kept'].sum()):,} of {N_DRAWS:,} draws."
    )


if __name__ == "__main__":
    main()
