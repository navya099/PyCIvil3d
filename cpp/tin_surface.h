#pragma once

#include <array>
#include <cstddef>
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
    std::vector<Point3d> vertices_;
    std::vector<std::array<std::size_t, 3>> triangles_;
};

}  // namespace pycivil3d
