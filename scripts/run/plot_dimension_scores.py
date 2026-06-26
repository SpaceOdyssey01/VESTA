from __future__ import annotations

import argparse
import csv
import textwrap
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np


# Resolve from this file so plotting works from the checked-out project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def read_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in [None, ""]:
            return default
        return float(value)
    except Exception:
        return default


def safe_filename(text: str) -> str:
    return (
        str(text)
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace(" ", "_")
        .replace(".", "_")
    )


def wrap_label(text: str, width: int = 12) -> str:
    return "\n".join(textwrap.wrap(str(text), width=width))


def infer_dimension(rows: List[Dict[str, Any]], fallback: str | None = None) -> str:
    if fallback:
        return fallback

    for row in rows:
        value = row.get("dimension")
        if value:
            return str(value)

    return "unknown_dimension"


def collect_by_subtype(
    rows: List[Dict[str, Any]],
    metric: str
) -> Dict[str, Dict[str, Dict[str, float]]]:
    data: Dict[str, Dict[str, Dict[str, float]]] = {}

    for row in rows:
        subtype = row.get("risk_subtype") or "unknown_subtype"
        model = row.get("target_model") or "unknown_model"
        authority_mode = row.get("authority_mode") or "unknown"
        value = to_float(row.get(metric), 0.0)

        data.setdefault(subtype, {})
        data[subtype].setdefault(model, {})
        data[subtype][model][authority_mode] = value

    return data


def get_metric_label(metric: str, user_label: str | None = None) -> str:
    if user_label:
        return user_label

    labels = {
        "unsafe_rate": "Unsafe Rate",
        "risk_score": "Risk Score",
        "attack_success_rate": "Attack Success Rate",
        "unsafe_tool_rate": "Unsafe Tool Rate",
        "avg_tool_calls": "Average Tool Calls"
    }

    return labels.get(metric, metric)


def get_y_limit(metric: str, values: List[float]) -> tuple[float, float]:
    if metric.endswith("_rate") or metric == "unsafe_rate":
        return 0.0, 1.08

    if metric.endswith("_score") or metric == "risk_score":
        return 0.0, 108.0

    max_value = max(values) if values else 1.0
    return 0.0, max_value * 1.12 if max_value > 0 else 1.0


def plot_one_subtype(
    subtype: str,
    model_data: Dict[str, Dict[str, float]],
    output_dir: Path,
    metric: str,
    metric_label: str,
    top_n: int | None = None,
    xtick_fontsize: int = 7,
    value_fontsize: int = 6,
    hide_zero_labels: bool = True
) -> None:
    authority_modes = sorted({
        mode
        for values in model_data.values()
        for mode in values.keys()
    })

    preferred_order = ["soft", "hard"]
    authority_modes = [
        mode for mode in preferred_order if mode in authority_modes
    ] + [
        mode for mode in authority_modes if mode not in preferred_order
    ]

    if not authority_modes:
        return

    rows: List[Dict[str, Any]] = []

    for model_name, values in model_data.items():
        row = {"model_name": model_name}
        for mode in authority_modes:
            row[mode] = values.get(mode, 0.0)
        row["_sort_value"] = max(row[mode] for mode in authority_modes)
        rows.append(row)

    rows.sort(key=lambda x: x["_sort_value"], reverse=True)

    if top_n is not None and top_n > 0:
        rows = rows[:top_n]

    if not rows:
        return

    model_names = [row["model_name"] for row in rows]
    x = np.arange(len(model_names))

    num_modes = len(authority_modes)
    total_width = 0.72
    bar_width = total_width / max(num_modes, 1)

    fig_width = max(9, len(model_names) * 0.68)
    fig, ax = plt.subplots(figsize=(fig_width, 5.0), dpi=300)

    bars_all = []
    mode_colors = {
        "soft": "#BFDBFE",
        "hard": "#3B82F6"
    }

    for idx, mode in enumerate(authority_modes):
        offset = (idx - (num_modes - 1) / 2) * bar_width
        values = [row[mode] for row in rows]

        bars = ax.bar(
            x + offset,
            values,
            bar_width,
            label=mode.capitalize(),
            color=mode_colors.get(mode),
            edgecolor="white",
            linewidth=1.0,
            alpha=0.95,
            zorder=3
        )

        bars_all.append(bars)

    ax.set_title(
        subtype.replace("_", " ").title(),
        fontsize=15,
        fontweight="bold",
        pad=14
    )

    ax.set_ylabel(metric_label, fontsize=11, labelpad=9)

    ax.set_xticks(x)
    ax.set_xticklabels(
        [wrap_label(name, width=10) for name in model_names],
        fontsize=xtick_fontsize,
        rotation=18,
        ha="right"
    )

    all_values = [
        row[mode]
        for row in rows
        for mode in authority_modes
    ]

    ymin, ymax = get_y_limit(metric, all_values)
    ax.set_ylim(ymin, ymax)

    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="y", linestyle="--", linewidth=0.75, alpha=0.25, zorder=0)
    ax.grid(axis="x", visible=False)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_alpha(0.3)
    ax.spines["bottom"].set_alpha(0.3)

    legend = ax.legend(
        loc="upper right",
        frameon=True,
        fancybox=True,
        framealpha=0.95,
        edgecolor="#dddddd",
        fontsize=10
    )
    legend.get_frame().set_facecolor("white")

    label_offset = 0.012 if ymax <= 2 else ymax * 0.012

    for bars in bars_all:
        for bar in bars:
            h = bar.get_height()

            if hide_zero_labels and abs(h) < 1e-9:
                continue

            label = f"{h:.2f}"

            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + label_offset,
                label,
                ha="center",
                va="bottom",
                fontsize=value_fontsize,
                color="#333333",
                fontweight="semibold"
            )

    fig.tight_layout()

    output_path = output_dir / f"{safe_filename(subtype)}_{safe_filename(metric)}.png"
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to scores.csv."
    )
    parser.add_argument(
        "--dimension",
        type=str,
        default=None,
        help="Dimension name. If omitted, infer from scores.csv."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Default: outputs/figures/<dimension>/"
    )
    parser.add_argument(
        "--metric",
        type=str,
        default="attack_success_rate",
        help="Metric column to plot. Default: attack_success_rate."
    )
    parser.add_argument(
        "--metric-label",
        type=str,
        default=None
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None
    )
    parser.add_argument(
        "--xtick-fontsize",
        type=int,
        default=7
    )
    parser.add_argument(
        "--value-fontsize",
        type=int,
        default=6
    )
    parser.add_argument(
        "--show-zero-labels",
        action="store_true"
    )

    args = parser.parse_args()

    input_path = resolve_path(args.input)

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    rows = read_csv(input_path)

    if not rows:
        raise SystemExit(f"No rows found in: {input_path}")

    if args.metric not in rows[0]:
        raise ValueError(
            f"Metric column not found: {args.metric}. "
            f"Available columns: {list(rows[0].keys())}"
        )

    dimension = infer_dimension(rows, fallback=args.dimension)

    if args.output_dir:
        output_dir = resolve_path(args.output_dir)
    else:
        output_dir = PROJECT_ROOT / "outputs" / "figures" / dimension

    output_dir.mkdir(parents=True, exist_ok=True)

    data = collect_by_subtype(rows, metric=args.metric)
    metric_label = get_metric_label(args.metric, args.metric_label)

    for subtype, model_data in sorted(data.items()):
        plot_one_subtype(
            subtype=subtype,
            model_data=model_data,
            output_dir=output_dir,
            metric=args.metric,
            metric_label=metric_label,
            top_n=args.top_n,
            xtick_fontsize=args.xtick_fontsize,
            value_fontsize=args.value_fontsize,
            hide_zero_labels=not args.show_zero_labels
        )

    print(f"All figures saved to: {output_dir}")


if __name__ == "__main__":
    main()
