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
    TinSurfaceTriangle,
    TinSurfaceTriangleCollection,
    TinSurfaceVertex,
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

    def test_index_rebuilds_after_surface_expands(self):
        self.add(*((x, y, x + 2 * y) for x in range(5) for y in range(5)))
        for x, y in ((0, 0), (4, 4), (2, 2.5), (3.25, 0.75)):
            self.assertAlmostEqual(self.surface.FindElevationAtXY(x, y), x + 2 * y)

        with self.assertRaises(PointNotOnEntityException):
            self.surface.FindElevationAtXY(5, 2)
        self.add((6, 0, 6), (6, 4, 14))
        self.assertAlmostEqual(self.surface.FindElevationAtXY(5, 2), 9)
        self.assertAlmostEqual(self.surface.FindElevationAtXY(2, 2.5), 7)
        with self.assertRaises(PointNotOnEntityException):
            self.surface.FindElevationAtXY(7, 2)

    def test_get_triangles_returns_mesh_snapshot(self):
        self.assertEqual(self.surface.GetTriangles(False).Count, 0)
        self.add((0, 0, 1), (2, 0, 2), (0, 2, 3))
        snapshot = self.surface.GetTriangles(False)
        self.assertIsInstance(snapshot, TinSurfaceTriangleCollection)
        self.assertEqual(snapshot.Count, 1)
        triangle, = snapshot
        self.assertIsInstance(triangle, TinSurfaceTriangle)
        self.assertTrue(triangle.IsVisible)
        self.assertIs(triangle.Surface, self.surface)
        vertices = (triangle.Vertex1, triangle.Vertex2, triangle.Vertex3)
        for vertex in vertices:
            self.assertIsInstance(vertex, TinSurfaceVertex)
            self.assertIs(vertex.Surface, self.surface)
        self.assertEqual(
            {(p.X, p.Y, p.Z) for p in (vertex.Location for vertex in vertices)},
            {(0, 0, 1), (2, 0, 2), (0, 2, 3)},
        )

        self.add((2, 2, 4))
        self.assertEqual(snapshot.Count, 1)
        self.assertEqual(self.surface.GetTriangles(True).Count, 2)
        self.assertEqual(self.surface.Triangles.Count, 2)
        with self.assertRaises(TypeError):
            self.surface.GetTriangles(None)
