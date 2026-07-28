#pragma once

#include "millui/native/types.hpp"

namespace millui::native::algo {

constexpr double kDefaultRetractClearanceMm = 2.0;

Paths plan_pocket(const PlanarFace& face, const Tool& tool, double step_over_mm,
                  double step_down_mm, double safe_z_mm, double ramp_angle_deg = 0.0,
                  PocketStrategy strategy = PocketStrategy::Spiral);
Paths plan_profile(const Polygon& boundary, const Tool& tool, double total_depth_mm,
                   double step_down_mm, double safe_z_mm, double ramp_angle_deg = 0.0);
Paths plan_drill(const std::vector<Hole>& holes, const Tool& tool, double peck_mm, double safe_z_mm,
                 double retract_clearance_mm = kDefaultRetractClearanceMm);
Paths plan_bore_helical(const Hole& hole, const Tool& tool, double step_down_mm, double safe_z_mm);

}  // namespace millui::native::algo
