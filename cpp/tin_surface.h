#pragma once

#include <array>
#include <cstddef>
#include <optional>
#include <stdexcept>
#include <vector>

namespace pycivil3d {

struct Point3d {
    double x;
    double y;
    double z;
};

class PointNotOnEntityException : public std::runtime_error {
    using std::runtime_error::runtime_error;
};

class TinMesh {
public:
    void add_vertices(const std::vector<Point3d>& locations);
    double elevation_at_xy(double x, double y) const;

private:
    struct Bounds {
        double min_x;
        double min_y;
        double max_x;
        double max_y;

        bool contains(double x, double y) const;
    };

    struct Triangle {
        std::array<std::size_t, 3> vertices;
        Bounds bounds;
        std::size_t order;
    };

    struct Node {
        Bounds bounds;
        std::size_t begin;
        std::size_t end;
        std::size_t left = 0;
        std::size_t right = 0;
    };

    struct TriangleIndex {
        std::vector<Triangle> triangles;
        std::vector<Node> nodes;

        std::size_t build(std::size_t begin, std::size_t end);
        void find(std::size_t node, double x, double y, const std::vector<Point3d>& points,
                  std::size_t& first_match, std::optional<double>& elevation) const;
    };

    std::vector<Point3d> vertices_;
    TriangleIndex index_;
};

}  // namespace pycivil3d
