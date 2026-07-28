#pragma once

#include <optional>
#include <span>
#include <utility>
#include <vector>

#include "millui/native/algo/geom2d.hpp"
#include "millui/native/types.hpp"

namespace millui::native::algo {

constexpr double kDefaultRetractClearanceMm = 2.0;
constexpr double kDefaultToolDiameterMm = 3.0;
constexpr double kDefaultStepDownCapMm = 3.0;
constexpr double kMinStepOverMm = 0.1;

struct PocketParams {
    double tool_diameter = 0.0;
    double tool_radius = 0.0;
    double step_down = 0.0;
    double step_over = 0.0;
    double depth = 0.0;

    [[nodiscard]] static PocketParams resolve(const Tool& tool, double depth_mm,
                                              double step_over_mm, double step_down_mm);
};

void emit_ramp_or_plunge(Path& moves, std::span<const Vec2> path, double prev_z, double target_z,
                         double ramp_angle_deg, double safe_z, double feed_xy, double feed_z,
                         bool keepdown = false);

[[nodiscard]] std::vector<Polygon> build_inset_rings(const ConvexPolygon& outermost,
                                                     double step_over);

[[nodiscard]] std::optional<std::pair<Vec2, Vec2>> find_sliver_span(const Polygon& last_ring,
                                                                    double tool_diameter);

[[nodiscard]] Paths plan_pocket(const PlanarFace& face, const Tool& tool, double step_over_mm,
                                double step_down_mm, double safe_z_mm, double ramp_angle_deg = 0.0,
                                PocketStrategy strategy = PocketStrategy::Spiral);
[[nodiscard]] Paths plan_profile(const Polygon& boundary, const Tool& tool, double total_depth_mm,
                                 double step_down_mm, double safe_z_mm,
                                 double ramp_angle_deg = 0.0);
[[nodiscard]] Paths plan_drill(const std::vector<Hole>& holes, const Tool& tool, double peck_mm,
                               double safe_z_mm,
                               double retract_clearance_mm = kDefaultRetractClearanceMm);
[[nodiscard]] Paths plan_bore_helical(const Hole& hole, const Tool& tool, double step_down_mm,
                                      double safe_z_mm);

}  // namespace millui::native::algo
