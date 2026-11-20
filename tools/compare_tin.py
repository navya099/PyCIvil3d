"""Compare a Pycivil3d surface with a reference TIN in JSON format."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

from pycivil3d import (
    Database,
    Point3d,
    Point3dCollection,
    PointNotOnEntityException,
    TinSurface,
)


def number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def coordinates(values, size, label):
    if not isinstance(values, list) or len(values) != size:
        raise ValueError(f"{label} must contain {size} coordinates")
    return tuple(number(value, label) for value in values)


def coordinate_array(values, size, label):
    if not isinstance(values, list):
        raise ValueError(f"{label} must be an array")
    return [coordinates(value, size, f"{label}[{i}]") for i, value in enumerate(values)]


def triangle_key(values, label):
    corners = coordinate_array(values, 3, label)
    if len(corners) != 3 or len({corner[:2] for corner in corners}) != 3:
        raise ValueError(f"{label} must contain three distinct XY vertices")
    return tuple(sorted(corners))


def surface_triangle_key(triangle):
    vertices = (triangle.Vertex1, triangle.Vertex2, triangle.Vertex3)
    locations = (vertex.Location for vertex in vertices)
    return tuple(sorted((point.X, point.Y, point.Z) for point in locations))


def compare(reference, abs_tol):
    points = coordinate_array(reference["points"], 3, "points")
    if not isinstance(reference["triangles"], list):
        raise ValueError("triangles must be an array")
    expected_triangles = Counter()
    for i, triangle in enumerate(reference["triangles"]):
        expected_triangles[triangle_key(triangle, f"triangles[{i}]")] += 1

    if not isinstance(reference["queries"], list):
        raise ValueError("queries must be an array")
    queries = []
    for i, query in enumerate(reference["queries"]):
        xy = coordinates(query["xy"], 2, f"queries[{i}].xy")
        elevation = query["elevation"]
        if elevation is not None:
            elevation = number(elevation, f"queries[{i}].elevation")
        triangle = query.get("triangle")
        if triangle is not None:
            triangle = triangle_key(triangle, f"queries[{i}].triangle")
        queries.append((xy, elevation, "triangle" in query, triangle))

    database = Database()
    surface = database.get_object(TinSurface.Create(database, "Reference comparison"))
    surface.AddVertices(Point3dCollection(Point3d(*point) for point in points))

    actual_triangles = Counter(map(surface_triangle_key, surface.GetTriangles(False)))

    differences = []
    for label, triangles in (
        ("missing", expected_triangles - actual_triangles),
        ("unexpected", actual_triangles - expected_triangles),
    ):
        if triangles:
            count = sum(triangles.values())
            first = min(triangles)
            differences.append(f"{count} {label} triangle(s), first {first}")

    for (x, y), expected, compare_triangle, expected_triangle in queries:
        try:
            actual = surface.FindElevationAtXY(x, y)
        except PointNotOnEntityException:
            actual = None
        if actual is None or expected is None:
            matches = actual is expected
        else:
            matches = math.isclose(actual, expected, rel_tol=0, abs_tol=abs_tol)
        if not matches:
            differences.append(f"XY ({x}, {y}) expected {expected!r}, got {actual!r}")

        if compare_triangle:
            try:
                triangle = surface.FindTriangleAtXY(x, y)
            except ValueError:
                actual_triangle = None
            else:
                actual_triangle = surface_triangle_key(triangle)
            if actual_triangle != expected_triangle:
                differences.append(
                    f"XY ({x}, {y}) expected triangle {expected_triangle!r}, "
                    f"got {actual_triangle!r}"
                )

    return differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, nargs="+")
    parser.add_argument("--abs-tol", type=float, default=1e-8, help="elevation tolerance")
    args = parser.parse_args()
    if not math.isfinite(args.abs_tol) or args.abs_tol < 0:
        parser.error("--abs-tol must be finite and nonnegative")

    status = 0
    for path in args.reference:
        try:
            reference = json.loads(path.read_text(encoding="utf-8-sig"))
            differences = compare(reference, args.abs_tol)
        except (OSError, ValueError, TypeError, KeyError, OverflowError, RuntimeError) as exc:
            print(f"{path} — error: {exc}", file=sys.stderr)
            status = 2
            continue
        if differences:
            for difference in differences:
                print(f"{path} — {difference}", file=sys.stderr)
            status = max(status, 1)
        else:
            print(f"{path} — match")
    return status


if __name__ == "__main__":
    sys.exit(main())
