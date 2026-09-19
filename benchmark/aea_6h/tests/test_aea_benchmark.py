import importlib.util
import unittest
from pathlib import Path


def load(name):
    path = Path(__file__).resolve().parents[1] / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


manifest_tool = load("build_aea_6h_manifest")
schedule_tool = load("build_aea_qa_schedule")


class AeaBenchmarkTests(unittest.TestCase):
    def test_order_session_boundaries_and_complete_groups(self):
        names = ["loc1_script1_seq2_rec1", "loc1_script1_seq1_rec1",
                 "loc2_script4_seq1_rec1", "loc1_script2_seq1_rec1"]
        urls = {"sequences": {name: {"video_main_rgb": {"file_size_bytes": 100}}
                               for name in names}}
        measurements = {name: (600.0, True) for name in names}
        result = manifest_tool.build(urls, [], measurements, 1000)
        rows = result["recordings"]
        self.assertEqual([r["sequence_id"] for r in rows], names[1::-1])
        self.assertEqual([r["session_boundary"] for r in rows], [True, False])
        self.assertEqual(result["total_duration_s"], 1200)
        self.assertEqual(len(result["inventory"]), 4)

    def test_schedule_causal_and_original_qa_unchanged(self):
        names = ["loc1_script1_seq1_rec1", "loc1_script1_seq2_rec1"]
        urls = {"sequences": {name: {"video_main_rgb": {"file_size_bytes": 100}}
                               for name in names}}
        manifest = manifest_tool.build(urls, [], {name: (1800, True) for name in names}, 3500)
        original = {"video_name": names[0], "question": "What?", "options": ["a", "b"],
                    "answer": "A", "keyframes": [{"timestamp": 10, "bbox": "1,2,3,4"}]}
        a = schedule_tool.build(manifest, [original], seed=42)
        b = schedule_tool.build(manifest, [original], seed=42)
        self.assertEqual(a, b)
        row = a["questions"][0]
        for key, value in original.items():
            self.assertEqual(row[key], value)
        self.assertGreater(row["ask_global_s"], row["evidence_global_s"])
        self.assertEqual(row["ask_global_s"] % 1200, 0)

    def test_invalid_evidence_rejected(self):
        name = "loc1_script1_seq1_rec1"
        manifest = manifest_tool.build(
            {"sequences": {name: {"video_main_rgb": {"file_size_bytes": 1}}}}, [],
            {name: (1800, True)}, 1000)
        with self.assertRaises(ValueError):
            schedule_tool.build(manifest, [{"video_name": name, "keyframes": [{"timestamp": 1900}]}])


if __name__ == "__main__":
    unittest.main()
