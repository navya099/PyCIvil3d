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
