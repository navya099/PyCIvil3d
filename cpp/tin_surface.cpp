#include "tin_surface.h"

#include <algorithm>
#include <cmath>
#include <map>
#include <utility>

#include "vendor/delaunator.hpp"

namespace pycivil3d {
namespace {

long double orient(const Point3d& a, const Point3d& b, double x, double y) {
    const auto dx = static_cast<long double>(b.x) - a.x;
    const auto dy = static_cast<long double>(b.y) - a.y;
    return dx * (static_cast<long double>(y) - a.y)
         - dy * (static_cast<long double>(x) - a.x);
}

std::vector<std::array<std::size_t, 3>> triangulate(const std::vector<Point3d>& points) {
    if (points.size() < 3) {
        return {};
    }
    const auto& first = points[0];
    const auto& second = points[1];
    if (std::all_of(points.begin() + 2, points.end(), [&](const Point3d& point) {
            return orient(first, second, point.x, point.y) == 0;
        })) {
        return {};
    }

    long double scale = 0;
    for (const auto& point : points) {
        scale = std::max({scale, std::abs(static_cast<long double>(point.x) - first.x),
                         std::abs(static_cast<long double>(point.y) - first.y)});
    }
    if (!std::isfinite(scale)) {
        throw std::invalid_argument("XY coordinate range is too large");
    }

    std::vector<double> coordinates;
    coordinates.reserve(2 * points.size());
    for (const auto& point : points) {
        coordinates.push_back(static_cast<double>((static_cast<long double>(point.x) - first.x) / scale));
        coordinates.push_back(static_cast<double>((static_cast<long double>(point.y) - first.y) / scale));
    }

    const delaunator::Delaunator mesh(coordinates);
    std::vector<std::array<std::size_t, 3>> triangles;
    triangles.reserve(mesh.triangles.size() / 3);
    std::vector<bool> used(points.size());
    for (std::size_t i = 0; i < mesh.triangles.size(); i += 3) {
        const auto a = mesh.triangles[i];
        auto b = mesh.triangles[i + 1];
        auto c = mesh.triangles[i + 2];
        const auto area = orient(points[a], points[b], points[c].x, points[c].y);
        if (area == 0 || !std::isfinite(area)) {
            throw std::invalid_argument("TIN contains a numerically degenerate triangle");
        }
        if (area < 0) {
            std::swap(b, c);
        }
        triangles.push_back({a, b, c});
        used[a] = used[b] = used[c] = true;
    }
    if (std::find(used.begin(), used.end(), false) != used.end()) {
        throw std::invalid_argument("TIN could not resolve all distinct XY coordinates");
    }
    return triangles;
}

}  // namespace

void TinMesh::add_vertices(const std::vector<Point3d>& locations) {
    std::vector<Point3d> vertices = vertices_;
    std::map<std::pair<double, double>, double> elevations;
    for (const auto& vertex : vertices) {
        elevations.emplace(std::make_pair(vertex.x, vertex.y), vertex.z);
    }
    for (const auto& point : locations) {
        if (!std::isfinite(point.x) || !std::isfinite(point.y) || !std::isfinite(point.z)) {
            throw std::invalid_argument("TIN vertices require finite coordinates");
        }
        const auto [entry, inserted] = elevations.emplace(std::make_pair(point.x, point.y), point.z);
        if (inserted) {
            vertices.push_back(point);
        } else if (entry->second != point.z) {
            throw std::invalid_argument("a TIN cannot store two elevations at the same XY");
        }
    }
    if (vertices.size() == vertices_.size()) {
        return;
    }

    auto triangles = triangulate(vertices);
    vertices_.swap(vertices);
    triangles_.swap(triangles);
}

double TinMesh::elevation_at_xy(double x, double y) const {
    if (!std::isfinite(x) || !std::isfinite(y)) {
        throw std::invalid_argument("XY coordinates must be finite");
    }
    for (const auto& triangle : triangles_) {
        const auto& a = vertices_[triangle[0]];
        const auto& b = vertices_[triangle[1]];
        const auto& c = vertices_[triangle[2]];
        if (x < std::min({a.x, b.x, c.x}) || x > std::max({a.x, b.x, c.x})
            || y < std::min({a.y, b.y, c.y}) || y > std::max({a.y, b.y, c.y})) {
            continue;
        }
        const auto wa = orient(b, c, x, y);
        const auto wb = orient(c, a, x, y);
        const auto wc = orient(a, b, x, y);
        if (wa >= 0 && wb >= 0 && wc >= 0) {
            const auto sum = wa + wb + wc;
            const auto elevation = (wa / sum) * a.z + (wb / sum) * b.z + (wc / sum) * c.z;
            return static_cast<double>(std::clamp(
                elevation, static_cast<long double>(std::min({a.z, b.z, c.z})),
                static_cast<long double>(std::max({a.z, b.z, c.z}))));
        }
    }
    throw PointNotOnEntityException("XY lies outside the triangulated surface");
}

}  // namespace pycivil3d
