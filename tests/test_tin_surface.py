import math
import unittest

from pycivil3d import (
    Database,
    ObjectId,
    Point3d,
    Point3dCollection,
    PointNotOnEntityException,
    SurfaceOperationAddTinMultipleVertices,
    TinSurface,
)


class TinSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.database = Database()
        self.surface_id = TinSurface.Create(self.database, "Existing Ground")
        self.surface = self.database.get_object(self.surface_id)

    def add(self, *locations):
        return self.surface.AddVertices(
            Point3dCollection(Point3d(*point) for point in locations)
        )

    def test_create_add_and_interpolate(self):
        self.assertIsInstance(self.surface_id, ObjectId)
        self.assertEqual(self.surface.ObjectId, self.surface_id)
        self.assertEqual(self.surface.Name, "Existing Ground")
        with self.assertRaises(ValueError):
            Database().get_object(self.surface_id)

        operation = self.add((0, 0, 100), (10, 0, 110), (0, 10, 120))
        self.assertIsInstance(operation, SurfaceOperationAddTinMultipleVertices)
        self.assertEqual(operation.Locations.Count, 3)
        self.assertEqual(self.surface.FindElevationAtXY(2, 3), 108)
        self.assertEqual(self.surface.FindElevationAtXY(5, 5), 115)
        self.assertEqual(self.surface.FindElevationAtXY(0, 10), 120)
        with self.assertRaises(PointNotOnEntityException):
            self.surface.FindElevationAtXY(6, 6)

    def test_build_from_collinear_points_across_batches(self):
        self.add((0, 0, 0), (5, 0, 5), (10, 0, 10))
        with self.assertRaises(PointNotOnEntityException):
            self.surface.FindElevationAtXY(5, 0)
        self.add((0, 10, 20), (10, 10, 30))
        self.assertAlmostEqual(self.surface.FindElevationAtXY(8, 7), 22)

    def test_failed_batch_preserves_surface(self):
        self.add((0, 0, 0), (10, 0, 10), (0, 10, 20))
        self.add((0, 0, 0))
        with self.assertRaises(ValueError):
            self.add((10, 10, 30), (0, 0, 5))
        with self.assertRaises(PointNotOnEntityException):
            self.surface.FindElevationAtXY(8, 8)
        with self.assertRaises(ValueError):
            self.add((math.nan, 0, 10))
        with self.assertRaises(ValueError):
            self.surface.FindElevationAtXY(0, math.inf)
        self.assertEqual(self.surface.FindElevationAtXY(2, 3), 8)

    def test_survey_coordinate_offsets(self):
        x, y = 1_000_000_000, -2_000_000_000
        self.add((x, y, 100), (x + 10, y, 110), (x, y + 10, 120))
        self.assertAlmostEqual(self.surface.FindElevationAtXY(x + 2, y + 3), 108)
