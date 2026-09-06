"""Plot comparable risk heatmaps from partitioned VESTA raw results.

No API calls and no changes to evaluation results. Relative paths resolve from
the repository root. Matplotlib is imported only when rendering.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCOPES = ("single_agent", "architecture_and_modules", "multi_agent_system",
          "external_environment", "interface_and_protocol")
LABELS = ("safe", "unsafe", "uncertain", "error")


def resolve_path(value):
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path):
    # Writers can replace a result file while an evaluation is running.
    for _ in range(3):
        before = path.stat()
        try:
            obj = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        after = path.stat()
        if (before.st_mtime_ns, before.st_size) == (after.st_mtime_ns, after.st_size):
            return obj
    raise ValueError(f"Cannot read a stable JSON snapshot: {path}. Retry after the writer finishes.")


def read_records(root, models=None, scopes=None, dimensions=None):
    """One record per scope/dimension/subtype/model/mode/instance.

    A successful rerun supersedes its stale error entry. Legacy records without
    IDs are retained individually, with a warning that they cannot be deduplicated.
    """
    if not root.is_dir():
        raise ValueError(f"Results directory does not exist: {root}")
    records = {}
    for scope in SCOPES:
        if scopes and scope not in scopes:
            continue
        base = root / scope
        for filename in ("errors.json", "results.json"):
            for path in sorted(base.glob(f"*/*/*/{filename}")):
                _, dimension, subtype, model, _ = path.relative_to(root).parts
                if (models and model not in models) or (dimensions and dimension not in dimensions):
                    continue
                items = read_json(path)
                if not isinstance(items, list):
                    raise ValueError(f"Expected a JSON list: {path}")
                anonymous = 0
                for index, item in enumerate(items):
                    if not isinstance(item, dict):
                        raise ValueError(f"Invalid record in {path}")
                    instance_id = item.get("instance_id")
                    if not instance_id:
                        anonymous += 1
                    identity = ("id", str(instance_id)) if instance_id else ("anonymous", str(path), index)
                    mode = str(item.get("authority_mode") or "unknown")
                    judge = item.get("final_judge_result") or {}
                    if not isinstance(judge, dict):
                        judge = {}
                    label = str(item.get("final_label") or judge.get("label") or
                                judge.get("final_label") or "error").lower().strip()
                    if filename == "errors.json" or label not in LABELS:
                        label = "error"
                    state = item.get("runtime_state") or {}
                    if not isinstance(state, dict):
                        state = {}
                    tool = bool(item.get("unsafe_tool_called") or item.get("executed_risk_events")
                                or state.get("forbidden_tool_called") or state.get("risk_events"))
                    key = (scope, dimension, subtype, model, mode, identity)
                    record = dict(scope=scope, dimension=dimension, subtype=subtype,
                                  model=model, mode=mode, label=label, unsafe_tool=tool)
                    if key not in records or label != "error":
                        records[key] = record
                if anonymous:
                    warnings.warn(f"{path}: {anonymous} records without instance_id retained without deduplication")
    return list(records.values())


def seed_families(root):
    """Seed hierarchy supplies rows even when no model has produced a result."""
    families = set()
    for scope in SCOPES:
        for path in (root / scope / "tasks").glob("*/*_seeds/seeds.json"):
            dimension, subtype_dir, _ = path.relative_to(root / scope / "tasks").parts
            families.add((scope, dimension, subtype_dir.removesuffix("_seeds")))
    return families


def make_cells(records, families, models, scopes=None, dimensions=None,
               authority_modes=("soft", "hard"), level="dimension",
               metric="unsafe_rate", denominator="valid", min_valid=1):
    def selected(scope, dimension):
        return (not scopes or scope in scopes) and (not dimensions or dimension in dimensions)

    def row_key(scope, dimension, subtype):
        return (scope, dimension, subtype) if level == "subtype" else (scope, dimension)

    rows = {row_key(*f) for f in families if selected(f[0], f[1])}
    grouped = defaultdict(list)
    for record in records:
        if record["model"] not in models or record["mode"] not in authority_modes:
            continue
        if not selected(record["scope"], record["dimension"]):
            continue
        key = row_key(record["scope"], record["dimension"], record["subtype"])
        rows.add(key)
        grouped[key, record["model"]].append(record)
    rows = sorted(rows)
    cells = []
    for key in rows:
        for model in models:
            group = grouped[key, model]
            counts = {label: sum(r["label"] == label for r in group) for label in LABELS}
            valid = sum(counts[label] for label in ("safe", "unsafe", "uncertain"))
            total = len(group)
            tool_count = sum(r["unsafe_tool"] for r in group if r["label"] != "error")
            denom = valid if denominator == "valid" else total
            numerator = counts["unsafe"] if metric == "unsafe_rate" else tool_count
            # Even all-attempts denominator must not paint all-error cells as 0%.
            value = numerator / denom if valid >= min_valid and denom else None
            status = ("missing" if not total else "all_error" if not valid else
                      "below_min_valid" if valid < min_valid else "ok")
            cells.append(dict(scope=key[0], dimension=key[1],
                              subtype=key[2] if len(key) == 3 else "", model=model,
                              authority_modes="+".join(authority_modes), total=total,
                              valid=valid, **counts, unsafe_tool_called=tool_count,
                              metric=metric, denominator=denominator, rate=value,
                              status=status))
    return rows, cells


def render(rows, cells, models, output_dir, prefix, rows_per_page, dpi, title, snapshot):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    lookup = {(c["scope"], c["dimension"], c["subtype"], c["model"]): c for c in cells}
    cmap = plt.get_cmap("YlOrRd").copy()
    cmap.set_bad("#D5D9DE")
    paths = []
    for start in range(0, len(rows), rows_per_page):
        subset = rows[start:start + rows_per_page]
        matrix = np.full((len(subset), len(models)), np.nan)
        for i, key in enumerate(subset):
            for j, model in enumerate(models):
                cell = lookup[(*key, model) if len(key) == 3 else (*key, "", model)]
                if cell["rate"] is not None:
                    matrix[i, j] = cell["rate"] * 100
        fig, ax = plt.subplots(figsize=(max(10, 6 + 1.8 * len(models)),
                                        max(4, 2.8 + .53 * len(subset))))
        im = ax.imshow(np.ma.masked_invalid(matrix), cmap=cmap, vmin=0, vmax=100, aspect="auto")
        ax.set_xticks(range(len(models)), models, fontsize=10)
        ax.xaxis.tick_top()
        ax.tick_params(top=True, bottom=False, length=0, pad=10)
        labels = [f"{key[1]} / {key[2]}" if len(key) == 3 else key[1] for key in subset]
        # Include scope to prevent similarly named dimensions being conflated.
        ax.set_yticks(range(len(subset)), [f"{key[0]}\n{label}" for key, label in zip(subset, labels)], fontsize=8)
        for i, key in enumerate(subset):
            for j, model in enumerate(models):
                c = lookup[(*key, model) if len(key) == 3 else (*key, "", model)]
                head = f"{100*c['rate']:.1f}%" if c["rate"] is not None else "N/A"
                ax.text(j, i, f"{head}\nn={c['valid']}, err={c['error']}",
                        ha="center", va="center", fontsize=9,
                        color="white" if c["rate"] is not None and c["rate"] >= .65 else "#17212C")
        ax.set_xticks(np.arange(-.5, len(models), 1), minor=True)
        ax.set_yticks(np.arange(-.5, len(subset), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.5)
        ax.tick_params(which="minor", length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        c0 = cells[0]
        metric_title = "Unsafe rate" if c0["metric"] == "unsafe_rate" else "Unsafe tool-call rate"
        fig.colorbar(im, ax=ax, fraction=.035, pad=.035, label=f"{metric_title} (%)")
        page = start // rows_per_page + 1
        pages = math.ceil(len(rows) / rows_per_page)
        fig.suptitle(title or f"VESTA risk heatmap | {c0['authority_modes']} | {page}/{pages}", fontsize=15, fontweight="bold")
        fig.text(.02, .015,
                 f"Snapshot: {snapshot} | Denominator: {c0['denominator']} | n = safe + unsafe + uncertain.\n"
                 "Gray = missing / all-error / below minimum n. Coverage may differ; rates are descriptive, not a matched ranking.",
                 fontsize=8, color="#48515C")
        fig.tight_layout(rect=(0, .07, 1, .95))
        stem = output_dir / f"{prefix}_{page:02d}"
        for extension in ("png", "pdf"):
            path = stem.with_suffix(f".{extension}")
            fig.savefig(path, dpi=dpi, bbox_inches="tight")
            paths.append(path)
        plt.close(fig)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", default="outputs/results")
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--models", nargs="+")
    parser.add_argument("--scopes", nargs="+", choices=SCOPES)
    parser.add_argument("--dimensions", nargs="+")
    parser.add_argument("--authority-modes", nargs="+", choices=("soft", "hard"), default=["soft", "hard"])
    parser.add_argument("--level", choices=("subtype", "dimension"), default="dimension",
                        help="Default: dimension (first-level risk categories); subtype shows second-level categories.")
    parser.add_argument("--metric", choices=("unsafe_rate", "unsafe_tool_rate"), default="unsafe_rate")
    parser.add_argument("--denominator", choices=("valid", "all"), default="valid",
                        help="valid excludes errors but includes uncertain; all includes errors (legacy scoring).")
    parser.add_argument("--min-valid", type=int, default=1)
    parser.add_argument("--rows-per-page", type=int, default=24)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--output-dir", default="outputs/figures/risk_heatmap")
    parser.add_argument("--title")
    args = parser.parse_args()
    if min(args.min_valid, args.rows_per_page, args.dpi) < 1:
        parser.error("--min-valid, --rows-per-page and --dpi must be positive")
    records = read_records(resolve_path(args.results_root), args.models, args.scopes, args.dimensions)
    if not records:
        parser.error("No records found in the supported partition layout")
    models = list(dict.fromkeys(args.models or sorted({r["model"] for r in records})))
    unknown = set(models) - {r["model"] for r in records}
    if unknown:
        warnings.warn(f"No records for models: {sorted(unknown)}; their cells will be gray")
    modes = list(dict.fromkeys(args.authority_modes))
    rows, cells = make_cells(records, seed_families(resolve_path(args.data_root)), models,
                             args.scopes, args.dimensions, modes, args.level, args.metric,
                             args.denominator, args.min_valid)
    if not rows:
        parser.error("No risk rows match these filters")
    snapshot = datetime.now().astimezone().isoformat(timespec="seconds")
    output = resolve_path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prefix = f"risk_heatmap_{args.level}_{'+'.join(modes)}_{args.metric}_{args.denominator}"
    csv_path = output / f"{prefix}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*cells[0], "snapshot"])
        writer.writeheader()
        writer.writerows(dict(c, snapshot=snapshot) for c in cells)
    for path in render(rows, cells, models, output, prefix, args.rows_per_page, args.dpi, args.title, snapshot):
        print(f"Saved: {path}")
    print(f"Saved: {csv_path}\nRows: {len(rows)}; models: {len(models)}; gray cells: {sum(c['rate'] is None for c in cells)}")


if __name__ == "__main__":
    main()
