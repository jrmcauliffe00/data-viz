"""Write the four figures from estimates.json. No Docker build is required."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "estimates.json").read_text())

KEPT_BLUE = "#1f4b99"
KEPT_LIGHT = "#6d93c7"
BUILD_ORANGE = "#c17b3a"
FAT_BROWN = "#8a5a44"
NODE_GREEN = "#4d6b45"
APT_GRAY = "#9aa0a6"
DEV_RED = "#9a3b2f"
CACHE_TAN = "#c4a574"
JS_GRAY = "#5c5c5c"
LINE = "#1a1a1a"
MUTED = "#4d4d4d"
GRID = "#e6e6e6"

SEGMENT_ORDER = [
    ("slim_base", "python:3.12-slim", KEPT_BLUE),
    ("streamlit_runtime", "Streamlit + pandas + numpy + pyarrow", KEPT_LIGHT),
    ("build_tools", "gcc / make / git / curl left in the image", BUILD_ORANGE),
    ("fat_debian_extra", "extra Debian in python:3.12 vs slim", FAT_BROWN),
    ("nodejs_npm", "apt nodejs + npm", NODE_GREEN),
    ("apt_lists", "uncleaned apt lists", APT_GRAY),
    ("jupyter_dev", "Jupyter, pytest, black", DEV_RED),
    ("pip_cache", "pip wheel cache", CACHE_TAN),
    ("node_modules", "frontend node_modules", JS_GRAY),
]

RECIPE_ORDER = ("bloated", "tutorial", "multistage")


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#333333",
            "axes.labelcolor": LINE,
            "xtick.color": "#333333",
            "ytick.color": "#333333",
            "text.color": LINE,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "axes.unicode_minus": False,
        }
    )


def recipe_total(key: str) -> float:
    components = DATA["components_mb"]
    return sum(
        row["mb"] for row in components.values() if key in row["kept_in"]
    )


def draw_layers(path: Path) -> None:
    components = DATA["components_mb"]
    labels = [DATA["recipes"][key]["label"] for key in RECIPE_ORDER]
    totals = [recipe_total(key) for key in RECIPE_ORDER]
    y = list(range(len(RECIPE_ORDER) - 1, -1, -1))

    fig, ax = plt.subplots(figsize=(10.6, 6.0))
    left = [0.0] * len(RECIPE_ORDER)
    for key, name, color in SEGMENT_ORDER:
        widths = [
            components[key]["mb"] if recipe in components[key]["kept_in"] else 0.0
            for recipe in RECIPE_ORDER
        ]
        ax.barh(
            y,
            widths,
            left=left,
            height=0.62,
            color=color,
            label=name,
            zorder=2,
        )
        left = [a + b for a, b in zip(left, widths)]

    for yi, total in zip(y, totals):
        ax.text(total + 30, yi, f"{total / 1000:.2f} GB", va="center", fontsize=9, color=MUTED)

    ax.set_yticks(y, labels)
    ax.set_xlabel("Uncompressed image size (MB)")
    ax.set_xlim(0, max(totals) * 1.18)
    ax.grid(axis="x", color=GRID, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title(
        "Same Streamlit app. Three Dockerfiles.",
        loc="left",
        fontsize=12,
    )
    handles = [Patch(facecolor=c, label=n) for _, n, c in SEGMENT_ORDER]
    fig.tight_layout(rect=(0, 0.28, 1, 1))
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=8,
        bbox_to_anchor=(0.5, 0.08),
    )
    fig.text(
        0.01,
        0.012,
        textwrap.fill(
            "Blue stays at runtime. The other slices are build tools, caches, or a JavaScript "
            "tree the process never imports. The 1.02 GB middle total is Streamlit's published "
            "tutorial image; its split and the other bars are composed from published pieces.",
            width=140,
        ),
        fontsize=7.5,
        color=MUTED,
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)


def draw_bases(path: Path) -> None:
    rows = DATA["base_images"]
    labels = [row["label"] for row in rows]
    uncompressed = [row["uncompressed_mb"] for row in rows]
    compressed = [row["compressed_mb"] for row in rows]
    y = list(range(len(rows) - 1, -1, -1))

    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    ax.barh(
        [yi + 0.16 for yi in y],
        uncompressed,
        height=0.30,
        color=FAT_BROWN,
        label="On disk (`docker images`)",
        zorder=2,
    )
    ax.barh(
        [yi - 0.16 for yi in y],
        compressed,
        height=0.30,
        color=KEPT_BLUE,
        label="Over the wire (`docker pull`)",
        zorder=2,
    )
    for yi, u, c in zip(y, uncompressed, compressed):
        ax.text(u + 12, yi + 0.16, f"{u:.0f} MB", va="center", fontsize=8, color=MUTED)
        ax.text(c + 12, yi - 0.16, f"{c:.0f} MB", va="center", fontsize=8, color=MUTED)

    ax.set_yticks(y, labels)
    ax.set_xlabel("Megabytes")
    ax.set_xlim(0, max(uncompressed) * 1.18)
    ax.grid(axis="x", color=GRID, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title("Official Python tags, before any app is installed", loc="left", fontsize=12)
    fig.tight_layout(rect=(0, 0.22, 1, 1))
    fig.legend(
        loc="lower center",
        ncol=2,
        frameon=False,
        fontsize=9,
        bbox_to_anchor=(0.5, 0.08),
    )
    fig.text(
        0.01,
        0.012,
        textwrap.fill(
            "Uncompressed: testdriven.io, python 3.12.2, docker images. "
            "Compressed: Docker Hub linux/amd64, python 3.12.14. "
            "The default tag is about 8× slim on disk and 10× alpine on the wire. "
            "Slim is the usual runtime base; alpine is smaller and uses musl, which some wheels do not ship.",
            width=130,
        ),
        fontsize=7.5,
        color=MUTED,
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)


def draw_bases_on_disk(path: Path) -> None:
    rows = DATA["base_images"]
    labels = [row["label"] for row in rows]
    uncompressed = [row["uncompressed_mb"] for row in rows]
    x = list(range(len(rows)))

    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    ax.bar(x, uncompressed, width=0.58, color=FAT_BROWN, zorder=2)
    for xi, u in zip(x, uncompressed):
        ax.text(
            xi,
            u + 18,
            f"{u:.0f} MB",
            ha="center",
            va="bottom",
            fontsize=9,
            color=MUTED,
        )

    ax.set_xticks(x, labels)
    ax.set_ylabel("Uncompressed image size (MB)")
    ax.set_ylim(0, max(uncompressed) * 1.18)
    ax.grid(axis="y", color=GRID, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title(
        "Official Python tags, before any app is installed",
        loc="left",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.14, 1, 1))
    fig.text(
        0.01,
        0.012,
        textwrap.fill(
            "testdriven.io, python 3.12.2, `docker images`. These are unpacked sizes on disk, "
            "not the compressed layers a `docker pull` transfers. The default tag is about "
            "8× slim. Slim is the usual runtime base; alpine is smaller and uses musl, "
            "which some wheels do not ship.",
            width=120,
        ),
        fontsize=7.5,
        color=MUTED,
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)


def pull_seconds(compressed_mb: float, bandwidth_mbit: float) -> float:
    model = DATA["pull_model"]
    return (
        model["intercept_ms"]
        + model["slope_ms_per_mb_per_mbit"] * (compressed_mb / bandwidth_mbit)
    ) / 1000.0


def draw_pull(path: Path) -> None:
    model = DATA["pull_model"]
    ratio = DATA["compression_ratio_for_estimates"]["ratio"]
    xs = list(range(0, 901, 5))

    fig, ax = plt.subplots(figsize=(9.4, 5.2))
    styles = {5: ("#9a3b2f", "-"), 20: ("#1f4b99", "-"), 100: ("#4d4d4d", "--")}
    for bw in model["bandwidths_mbit"]:
        color, ls = styles[bw]
        ys = [pull_seconds(x, bw) for x in xs]
        label = f"{bw} Mbit/s"
        if bw not in model["fit_bandwidths_mbit"]:
            label += " (same equation, outside the fit)"
        ax.plot(xs, ys, color=color, ls=ls, lw=1.6, label=label, zorder=2)

    marks = [
        ("python:3.12-alpine", DATA["base_images"][0]["compressed_mb"], "measured", 55, 85),
        ("python:3.12-slim", DATA["base_images"][1]["compressed_mb"], "measured", 230, 12),
        ("python:3.12", DATA["base_images"][2]["compressed_mb"], "measured", 520, 115),
        ("multi-stage app", recipe_total("multistage") * ratio, "estimated", 140, 185),
        ("bloated app", recipe_total("bloated") * ratio, "estimated", 620, 300),
    ]
    bw_mark = 20
    for name, mb, kind, tx, ty in marks:
        sec = pull_seconds(mb, bw_mark)
        facecolor = KEPT_BLUE if kind == "measured" else "white"
        ax.scatter(
            [mb],
            [sec],
            s=42,
            facecolors=facecolor,
            edgecolors=LINE,
            linewidths=1.1,
            zorder=4,
        )
        ax.annotate(
            f"{name}\n{mb:.0f} MB → {sec:.0f} s",
            xy=(mb, sec),
            xytext=(tx, ty),
            textcoords="data",
            fontsize=7.5,
            color=MUTED,
            ha="left",
            va="center",
            arrowprops={"arrowstyle": "-", "color": "#b0b0b0", "lw": 0.8},
        )

    ax.set_xlim(0, 900)
    ax.set_ylim(0, 400)
    ax.set_xlabel("Compressed image size (MB)")
    ax.set_ylabel("Cold pull time (seconds)")
    ax.grid(color=GRID, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title(
        "At a fixed bandwidth, pull time is close to linear in compressed size",
        loc="left",
        fontsize=12,
    )
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout(rect=(0, 0.18, 1, 1))
    fig.text(
        0.01,
        0.012,
        textwrap.fill(
            "pull_s = 4.391 + 7.794 × (MB / Mbit). Reddy 2026, Kind + local registry, "
            "R² = 0.95 on 5 and 20 Mbit/s (N=48). The intercept is registry overhead, not "
            "transfer. Open circles use 0.35 × uncompressed for the composed Streamlit images. "
            "Docker Hub adds token/manifest round trips; tiny images stay latency-bound.",
            width=135,
        ),
        fontsize=7.5,
        color=MUTED,
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> None:
    style()
    draw_layers(HERE / "bloated_layers.png")
    draw_bases(HERE / "base_images.png")
    draw_bases_on_disk(HERE / "base_images_on_disk.png")
    draw_pull(HERE / "pull_time.png")
    print("wrote bloated_layers.png")
    print("wrote base_images.png")
    print("wrote base_images_on_disk.png")
    print("wrote pull_time.png")
    print(f"bloated {recipe_total('bloated'):.0f} MB")
    print(f"tutorial {recipe_total('tutorial'):.0f} MB")
    print(f"multistage {recipe_total('multistage'):.0f} MB")


if __name__ == "__main__":
    main()
