#pragma once

#include <optional>
#include <vector>

#include "millui/native/types.hpp"

namespace millui::native::algo {

inline constexpr double kEps = 1e-9;
inline constexpr double kMinStepDownMm = 0.01;

struct Bounds {
    double minx = 0.0;
    double miny = 0.0;
    double maxx = 0.0;
    double maxy = 0.0;
};

[[nodiscard]] Bounds bounds_of(const Polygon& poly);
[[nodiscard]] double seg_length(const Vec2& a, const Vec2& b) noexcept;
[[nodiscard]] double shoelace_area(const Polygon& poly);
[[nodiscard]] bool is_convex(const Polygon& poly);
[[nodiscard]] Polygon ensure_cw(const Polygon& poly);
[[nodiscard]] Polygon strip_closing_vertex(const Polygon& poly);
[[nodiscard]] Polygon inset_convex(const Polygon& poly, double offset);
[[nodiscard]] size_t longest_edge_index(const Polygon& poly);
[[nodiscard]] std::vector<double> scanline_intersections(const Polygon& poly, double y);
[[nodiscard]] std::vector<double> build_z_levels(double depth, double step_down);

class ConvexPolygon {
   public:
    [[nodiscard]] static std::optional<ConvexPolygon> try_from(const Polygon& poly);
    [[nodiscard]] const Polygon& points() const { return points_; }

   private:
    explicit ConvexPolygon(Polygon points) : points_(std::move(points)) {}
    Polygon points_;
};

[[nodiscard]] Polygon inset(const ConvexPolygon& poly, double offset);

}  // namespace millui::native::algo
