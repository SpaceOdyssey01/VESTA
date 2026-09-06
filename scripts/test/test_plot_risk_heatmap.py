import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "run" / "plot_risk_heatmap.py"
spec = importlib.util.spec_from_file_location("heatmap", MODULE)
heatmap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(heatmap)


class HeatmapTests(unittest.TestCase):
    def record(self, label, model="a", mode="soft", subtype="s"):
        return dict(scope="external_environment", dimension="d", subtype=subtype,
                    model=model, mode=mode, label=label, unsafe_tool=label == "unsafe")

    def test_weighted_counts_and_missing(self):
        records = [self.record("unsafe")] + [self.record("safe", mode="hard") for _ in range(3)]
        _, cells = heatmap.make_cells(records, set(), ["a", "b"])
        self.assertEqual(cells[0]["rate"], .25)
        self.assertIsNone(cells[1]["rate"])
        self.assertEqual(cells[1]["status"], "missing")

    def test_errors_uncertain_and_denominators(self):
        records = [self.record(label) for label in ("unsafe", "uncertain", "error")]
        _, cells = heatmap.make_cells(records, set(), ["a"])
        self.assertEqual(cells[0]["rate"], .5)
        self.assertEqual(cells[0]["error"], 1)
        _, cells = heatmap.make_cells(records, set(), ["a"], denominator="all")
        self.assertAlmostEqual(cells[0]["rate"], 1 / 3)
        for denom in ("all", "valid"):
            _, cells = heatmap.make_cells([self.record("error")], set(), ["a"], denominator=denom)
            self.assertIsNone(cells[0]["rate"])
            self.assertEqual(cells[0]["status"], "all_error")

    def test_filter_and_seed_only_rows(self):
        families = {("external_environment", "d", "s"), ("external_environment", "d", "missing")}
        records = [self.record("unsafe"), self.record("safe", mode="hard")]
        _, cells = heatmap.make_cells(records, families, ["a"], authority_modes=["hard"], level="subtype")
        self.assertEqual([c["rate"] for c in cells], [None, 0])
        _, cells = heatmap.make_cells(records, families, ["a"], level="dimension")
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0]["rate"], .5)

    def test_default_merges_second_level_subtypes(self):
        records = [self.record("unsafe", subtype="s1")]
        records += [self.record("safe", subtype="s2") for _ in range(3)]
        rows, cells = heatmap.make_cells(records, set(), ["a"])
        self.assertEqual(rows, [("external_environment", "d")])
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0]["subtype"], "")
        self.assertEqual(cells[0]["valid"], 4)
        self.assertEqual(cells[0]["rate"], .25)

    def test_minimum_and_tool_metric(self):
        record = self.record("unsafe")
        record["unsafe_tool"] = False
        _, cells = heatmap.make_cells([record], set(), ["a"], metric="unsafe_tool_rate")
        self.assertEqual(cells[0]["rate"], 0)
        _, cells = heatmap.make_cells([record], set(), ["a"], min_valid=2)
        self.assertEqual(cells[0]["status"], "below_min_valid")
        self.assertIsNone(cells[0]["rate"])

    def test_result_supersedes_stale_error_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "external_environment/d/s/a"
            path.mkdir(parents=True)
            item = dict(instance_id="i", authority_mode="soft", final_label="safe")
            (path / "errors.json").write_text(json.dumps([item]))
            (path / "results.json").write_text(json.dumps([item, item]))
            records = heatmap.read_records(Path(tmp))
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["label"], "safe")
            (path / "results.json").write_text(json.dumps([dict(item, instance_id=None)] * 2))
            with self.assertWarns(UserWarning):
                records = heatmap.read_records(Path(tmp))
            self.assertEqual(len(records), 3)  # two anonymous results plus one known error
            (path / "results.json").write_text('{"unexpected":1}')
            with self.assertRaises(ValueError):
                heatmap.read_records(Path(tmp))


if __name__ == "__main__":
    unittest.main()
