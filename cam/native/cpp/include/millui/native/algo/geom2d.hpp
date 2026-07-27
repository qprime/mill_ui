#pragma once

#include "millui/native/types.hpp"

#include <optional>
#include <vector>

namespace millui::native::algo {

inline constexpr double kEps = 1e-9;

struct Bounds {
  double minx = 0.0;
  double miny = 0.0;
  double maxx = 0.0;
  double maxy = 0.0;
};

Bounds bounds_of(const Polygon& poly);
double seg_length(const Vec2& a, const Vec2& b);
double shoelace_area(const Polygon& poly);
bool is_convex(const Polygon& poly);
Polygon ensure_cw(const Polygon& poly);
Polygon strip_closing_vertex(const Polygon& poly);
Polygon inset_convex(const Polygon& poly, double offset);
size_t longest_edge_index(const Polygon& poly);
std::vector<double> scanline_intersections(const Polygon& poly, double y);
std::vector<double> build_z_levels(double depth, double step_down);

class ConvexPolygon {
 public:
  static std::optional<ConvexPolygon> try_from(const Polygon& poly);
  const Polygon& points() const { return points_; }

 private:
  explicit ConvexPolygon(Polygon points) : points_(std::move(points)) {}
  Polygon points_;
};

Polygon inset(const ConvexPolygon& poly, double offset);

}  // namespace millui::native::algo
