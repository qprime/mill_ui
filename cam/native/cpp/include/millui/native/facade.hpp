#pragma once

#include <limits>
#include <memory>
#include <string>
#include <vector>

namespace millui::native {

constexpr double kToleranceMm = 0.01;

struct Vec2 {
  double x = 0.0;
  double y = 0.0;
};
using Polygon = std::vector<Vec2>;

struct PlanarFace {
  double z = 0.0;
  double depth = 0.0;
  double safe_z = 5.0;
  Polygon outer;
  std::vector<Polygon> holes;
};

struct Hole {
  double x = 0.0;
  double y = 0.0;
  double diameter = 0.0;
  double depth = 0.0;
};

struct Tool {
  double diameter = 0.0;
  double rpm = 0.0;
  double feed_xy = 0.0;
  double feed_z = 0.0;
  std::string kind;
};

struct PostConfig {
  std::string unit;  // "mm" or "inch"
  double safe_z = 5.0;
  int prec = 3;
  std::vector<std::string> header;
  std::vector<std::string> footer;
};

struct PathMove {
  std::string kind;  // comment|set_rpm|set_feed|rapid|cut|retract|dwell
  double x = std::numeric_limits<double>::quiet_NaN();
  double y = std::numeric_limits<double>::quiet_NaN();
  double z = std::numeric_limits<double>::quiet_NaN();
  double feed = std::numeric_limits<double>::quiet_NaN();
  double rpm = std::numeric_limits<double>::quiet_NaN();
  double seconds = std::numeric_limits<double>::quiet_NaN();
  std::string text;
};
using Path = std::vector<PathMove>;
using Paths = std::vector<Path>;

struct Model {
  std::string source_path;
};

struct Setup {
  double tol_mm = kToleranceMm;
  double safe_z = 5.0;
};

std::unique_ptr<Model> load_step(const std::string& path);
std::unique_ptr<Setup> make_setup(const Model& model, double tol_mm = kToleranceMm);

std::vector<PlanarFace> detect_planar(const Model& model, const Setup& setup, double tol_mm = kToleranceMm);
std::vector<Hole> detect_holes(const Model& model, const Setup& setup, double tol_mm = kToleranceMm);

std::vector<Polygon> offset_inset(const Polygon& poly, double radius_mm);
std::vector<Polygon> offset_outset(const Polygon& poly, double radius_mm);

enum class PocketStrategy { Raster, Spiral };
Paths plan_pocket(const PlanarFace& face, const Tool& tool, double step_over_mm, double step_down_mm, double safe_z_mm, double ramp_angle_deg = 0.0, PocketStrategy strategy = PocketStrategy::Spiral);
Paths plan_profile(const Polygon& boundary, const Tool& tool, double total_depth_mm, double step_down_mm, double safe_z_mm, double ramp_angle_deg = 0.0);
Paths plan_drill(const std::vector<Hole>& holes, const Tool& tool, double peck_mm, double safe_z_mm);
Paths plan_bore_helical(const Hole& hole, const Tool& tool, double step_down_mm, double safe_z_mm);

std::string post_gcode(const Paths& paths, const PostConfig& cfg);

std::string create_stock(double minx, double miny, double maxx, double maxy, double pitch_mm);
Paths link_keepdown(const Paths& paths, double safe_z, double min_clearance);
Paths fit_arcs(const Paths& paths, double tol_mm);

}  // namespace millui::native
