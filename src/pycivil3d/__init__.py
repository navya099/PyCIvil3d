"""Headless Civil 3D-style geometry."""

from dataclasses import dataclass
from typing import Iterable, Iterator

from ._core import Point3d, PointNotOnEntityException, _TinMesh

__all__ = [
    "Database",
    "ObjectId",
    "Point3d",
    "Point3dCollection",
    "PointNotOnEntityException",
    "SurfaceOperationAddTinMultipleVertices",
    "TinSurface",
    "TinSurfaceObject",
    "TinSurfaceTriangle",
    "TinSurfaceTriangleCollection",
    "TinSurfaceVertex",
]


class Point3dCollection:
    def __init__(self, points: Iterable[Point3d] = ()):
        self._points: list[Point3d] = []
        for point in points:
            self.Add(point)

    def Add(self, value: Point3d) -> int:
        if not isinstance(value, Point3d):
            raise TypeError("value must be a Point3d")
        index = len(self._points)
        self._points.append(value)
        return index

    @property
    def Count(self) -> int:
        return len(self._points)

    def __getitem__(self, index: int) -> Point3d:
        return self._points[index]

    def __iter__(self) -> Iterator[Point3d]:
        return iter(self._points)

    def __len__(self) -> int:
        return self.Count


@dataclass(frozen=True)
class ObjectId:
    _database_key: object
    _index: int


class Database:
    """In-memory object store for standalone use."""

    def __init__(self):
        self._key = object()
        self._surfaces: list[TinSurface] = []

    def get_object(self, object_id: ObjectId) -> "TinSurface":
        if not isinstance(object_id, ObjectId):
            raise TypeError("object_id must be an ObjectId")
        if object_id._database_key is not self._key:
            raise ValueError("ObjectId belongs to another database")
        if not 0 <= object_id._index < len(self._surfaces):
            raise ValueError("ObjectId does not identify an object in this database")
        return self._surfaces[object_id._index]


class SurfaceOperationAddTinMultipleVertices:
    def __init__(self, locations: Point3dCollection):
        self._locations = tuple(locations)

    @property
    def Locations(self) -> Point3dCollection:
        return Point3dCollection(self._locations)


class TinSurfaceObject:
    def __init__(self, surface: "TinSurface"):
        self._surface = surface

    @property
    def Surface(self) -> "TinSurface":
        return self._surface


class TinSurfaceVertex(TinSurfaceObject):
    def __init__(self, surface: "TinSurface", location: Point3d):
        super().__init__(surface)
        self._location = location

    @property
    def Location(self) -> Point3d:
        return self._location


class TinSurfaceTriangle(TinSurfaceObject):
    def __init__(self, surface: "TinSurface", a: Point3d, b: Point3d, c: Point3d):
        super().__init__(surface)
        self._vertices = tuple(TinSurfaceVertex(surface, point) for point in (a, b, c))

    @property
    def Vertex1(self) -> TinSurfaceVertex:
        return self._vertices[0]

    @property
    def Vertex2(self) -> TinSurfaceVertex:
        return self._vertices[1]

    @property
    def Vertex3(self) -> TinSurfaceVertex:
        return self._vertices[2]

    @property
    def IsVisible(self) -> bool:
        return True


class TinSurfaceTriangleCollection:
    def __init__(self, surface: "TinSurface", locations: Iterable[Iterable[Point3d]]):
        self._surface = surface
        self._locations = tuple(locations)

    @property
    def Count(self) -> int:
        return len(self._locations)

    def __len__(self) -> int:
        return self.Count

    def __iter__(self) -> Iterator[TinSurfaceTriangle]:
        return (TinSurfaceTriangle(self._surface, *points) for points in self._locations)


class TinSurface:
    def __init__(self, surface_name: str, object_id: ObjectId):
        self._name = surface_name
        self._object_id = object_id
        self._mesh = _TinMesh()

    @staticmethod
    def Create(database: Database, surfaceName: str) -> ObjectId:
        if not isinstance(database, Database):
            raise TypeError("database must be a Database")
        if not isinstance(surfaceName, str):
            raise TypeError("surfaceName must be a string")
        if not surfaceName:
            raise ValueError("surfaceName must be nonempty")

        object_id = ObjectId(database._key, len(database._surfaces))
        database._surfaces.append(TinSurface(surfaceName, object_id))
        return object_id

    @property
    def Name(self) -> str:
        return self._name

    @property
    def ObjectId(self) -> ObjectId:
        return self._object_id

    def AddVertices(
        self, locations: Point3dCollection
    ) -> SurfaceOperationAddTinMultipleVertices:
        if not isinstance(locations, Point3dCollection):
            raise TypeError("locations must be a Point3dCollection")
        operation = SurfaceOperationAddTinMultipleVertices(locations)
        self._mesh.add_vertices(operation._locations)
        return operation

    def FindElevationAtXY(self, x: float, y: float) -> float:
        return self._mesh.elevation_at_xy(x, y)

    def FindTriangleAtXY(self, x: float, y: float) -> TinSurfaceTriangle:
        try:
            triangle_at_xy = self._mesh.triangle_at_xy
        except AttributeError as exc:
            raise RuntimeError(
                "The Pycivil3d C++ extension does not support FindTriangleAtXY. "
                "From the repository root, rebuild it in the active environment with "
                "'python -m pip install --no-cache-dir --force-reinstall -e .'."
            ) from exc
        return TinSurfaceTriangle(self, *triangle_at_xy(x, y))

    def GetTriangles(self, includeInvisible: bool) -> TinSurfaceTriangleCollection:
        if not isinstance(includeInvisible, bool):
            raise TypeError("includeInvisible must be a bool")
        return TinSurfaceTriangleCollection(self, self._mesh.triangle_locations())

    @property
    def Triangles(self) -> TinSurfaceTriangleCollection:
        return self.GetTriangles(False)
