#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "tin_surface.h"

namespace py = pybind11;
using namespace pycivil3d;

PYBIND11_MODULE(_core, module) {
    py::register_exception<PointNotOnEntityException>(module, "PointNotOnEntityException");

    py::class_<Point3d>(module, "Point3d")
        .def(py::init([](double x, double y, double z) { return Point3d{x, y, z}; }),
             py::arg("x"), py::arg("y"), py::arg("z"))
        .def_readonly("X", &Point3d::x)
        .def_readonly("Y", &Point3d::y)
        .def_readonly("Z", &Point3d::z)
        .def("__eq__", [](const Point3d& left, const Point3d& right) {
            return left.x == right.x && left.y == right.y && left.z == right.z;
        }, py::is_operator());

    py::class_<TinMesh>(module, "_TinMesh")
        .def(py::init<>())
        .def("add_vertices", &TinMesh::add_vertices)
        .def("elevation_at_xy", &TinMesh::elevation_at_xy)
        .def("triangle_locations", &TinMesh::triangle_locations);
}
