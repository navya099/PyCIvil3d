import json
from pathlib import Path
import unittest

from tools.compare_tin import compare


class Civil3dReferenceTests(unittest.TestCase):
    def test_cocircular_surfaces_match_civil3d(self):
        fixtures = Path(__file__).parent / "fixtures"
        for order in ("abcd", "bcda"):
            name = f"tin_cocircular_{order}.json"
            with self.subTest(order=order):
                source = json.loads(
                    (fixtures / "civil3d_inputs" / name).read_text(encoding="utf-8")
                )
                reference = json.loads(
                    (fixtures / "civil3d_reference" / name).read_text(encoding="utf-8-sig")
                )
                self.assertEqual(reference["points"], source["points"])
                self.assertEqual(
                    [query["xy"] for query in reference["queries"]],
                    [query["xy"] for query in source["queries"]],
                )
                differences = compare(reference, abs_tol=1e-8)
                self.assertFalse(differences, "\n".join(differences))

    def test_compare_distinguishes_shared_edge_triangles(self):
        path = Path(__file__).parent / "fixtures/civil3d_reference/tin_cocircular_abcd.json"
        reference = json.loads(path.read_text(encoding="utf-8"))
        center = reference["queries"][0]
        reference["queries"][-1]["triangle"] = None

        results = []
        for triangle in reference["triangles"]:
            center["triangle"] = list(reversed(triangle))
            results.append(compare(reference, abs_tol=1e-8))

        matching = [result for result in results if not result]
        mismatching = [result for result in results if result]
        self.assertEqual(len(matching), 1)
        self.assertEqual(len(mismatching), 1)
        self.assertEqual(len(mismatching[0]), 1)
        self.assertIn("XY (5.0, 5.0) expected triangle", mismatching[0][0])

        center["triangle"] = None
        self.assertIn("expected triangle None", compare(reference, abs_tol=1e-8)[0])
