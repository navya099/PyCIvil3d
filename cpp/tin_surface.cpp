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

    const auto triangles = triangulate(vertices);
    TriangleIndex index;
    index.triangles.reserve(triangles.size());
    for (const auto& triangle : triangles) {
        const auto& a = vertices[triangle[0]];
        const auto& b = vertices[triangle[1]];
        const auto& c = vertices[triangle[2]];
        const Bounds bounds{std::min({a.x, b.x, c.x}), std::min({a.y, b.y, c.y}),
                            std::max({a.x, b.x, c.x}), std::max({a.y, b.y, c.y})};
        index.triangles.push_back({triangle, bounds, index.triangles.size()});
    }
    if (!triangles.empty()) {
        index.build(0, triangles.size());
    }

    vertices_.swap(vertices);
    index_ = std::move(index);
}

bool TinMesh::Bounds::contains(double x, double y) const {
    return x >= min_x && x <= max_x && y >= min_y && y <= max_y;
}

std::size_t TinMesh::TriangleIndex::build(std::size_t begin, std::size_t end) {
    constexpr std::size_t leaf_size = 8;
    Bounds bounds = triangles[begin].bounds;
    for (std::size_t i = begin + 1; i < end; ++i) {
        const auto& box = triangles[i].bounds;
        bounds.min_x = std::min(bounds.min_x, box.min_x);
        bounds.min_y = std::min(bounds.min_y, box.min_y);
        bounds.max_x = std::max(bounds.max_x, box.max_x);
        bounds.max_y = std::max(bounds.max_y, box.max_y);
    }

    const auto node = nodes.size();
    nodes.push_back({bounds, begin, end});
    if (end - begin > leaf_size) {
        const auto middle = begin + (end - begin) / 2;
        const bool split_x = static_cast<long double>(bounds.max_x) - bounds.min_x
                           >= static_cast<long double>(bounds.max_y) - bounds.min_y;
        const auto center = [split_x](const Triangle& triangle) {
            const auto& box = triangle.bounds;
            // Halving before addition keeps the midpoint finite for large coordinates.
            return split_x ? box.min_x / 2 + box.max_x / 2 : box.min_y / 2 + box.max_y / 2;
        };
        std::nth_element(triangles.begin() + begin, triangles.begin() + middle,
                         triangles.begin() + end, [&](const Triangle& a, const Triangle& b) {
            return center(a) < center(b);
        });
        const auto left = build(begin, middle);
        const auto right = build(middle, end);
        nodes[node].left = left;
        nodes[node].right = right;
    }
    return node;
}

void TinMesh::TriangleIndex::find(std::size_t node, double x, double y,
                                  const std::vector<Point3d>& points, TriangleMatch& match) const {
    const auto& entry = nodes[node];
    if (!entry.bounds.contains(x, y)) {
        return;
    }
    if (entry.left != 0) {
        find(entry.left, x, y, points, match);
        find(entry.right, x, y, points, match);
        return;
    }

    for (std::size_t i = entry.begin; i < entry.end; ++i) {
        const auto& triangle = triangles[i];
        // Preserve the original triangle order for queries on shared edges and vertices.
        if ((match.triangle && triangle.order >= match.triangle->order)
            || !triangle.bounds.contains(x, y)) {
            continue;
        }
        const auto& a = points[triangle.vertices[0]];
        const auto& b = points[triangle.vertices[1]];
        const auto& c = points[triangle.vertices[2]];
        const auto wa = orient(b, c, x, y);
        const auto wb = orient(c, a, x, y);
        const auto wc = orient(a, b, x, y);
        if (wa >= 0 && wb >= 0 && wc >= 0) {
            match = {&triangle, {wa, wb, wc}};
        }
    }
}

TinMesh::TriangleMatch TinMesh::find_triangle(double x, double y) const {
    if (!std::isfinite(x) || !std::isfinite(y)) {
        throw std::invalid_argument("XY coordinates must be finite");
    }
    TriangleMatch match;
    if (!index_.nodes.empty()) {
        index_.find(0, x, y, vertices_, match);
    }
    return match;
}

double TinMesh::elevation_at_xy(double x, double y) const {
    const auto match = find_triangle(x, y);
    if (!match.triangle) {
        throw PointNotOnEntityException("XY lies outside the triangulated surface");
    }

    const auto [a, b, c] = locations(*match.triangle);
    const auto [wa, wb, wc] = match.weights;
    const auto sum = wa + wb + wc;
    const auto value = (wa / sum) * a.z + (wb / sum) * b.z + (wc / sum) * c.z;
    return static_cast<double>(std::clamp(
        value, static_cast<long double>(std::min({a.z, b.z, c.z})),
        static_cast<long double>(std::max({a.z, b.z, c.z}))));
}

std::array<Point3d, 3> TinMesh::triangle_at_xy(double x, double y) const {
    const auto match = find_triangle(x, y);
    if (!match.triangle) {
        throw std::invalid_argument("no TIN triangle contains the specified XY");
    }
    return locations(*match.triangle);
}

std::array<Point3d, 3> TinMesh::locations(const Triangle& triangle) const {
    const auto& indices = triangle.vertices;
    return {vertices_[indices[0]], vertices_[indices[1]], vertices_[indices[2]]};
}

std::vector<std::array<Point3d, 3>> TinMesh::triangle_locations() const {
    std::vector<std::array<Point3d, 3>> triangles(index_.triangles.size());
    for (const auto& triangle : index_.triangles) {
        triangles[triangle.order] = locations(triangle);
    }
    return triangles;
}

}  // namespace pycivil3d
