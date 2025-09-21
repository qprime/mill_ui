#include "millui/native/facade.hpp"

#include "millui/native/algo/plan_2d.hpp"
#include "millui/native/algo/post_gcode.hpp"
#include "millui/native/backends/occt/occt_backend.hpp"
#include "millui/native/geom2d/clipper2_wrap.hpp"

#include <stdexcept>

namespace millui::native {

std::unique_ptr<Model> load_step(const std::string& path) {
  auto result = occt::load_step(path);
  return std::move(result.model);
}

std::unique_ptr<Setup> make_setup(const Model& model, double tol_mm) {
  auto setup = occt::make_setup(model, tol_mm);
  if (setup) {
    setup->tol_mm = tol_mm;
  }
  return setup;
}

std::vector<PlanarFace> detect_planar(const Model& model, const Setup& setup, double tol_mm) {
  return occt::detect_planar(model, setup, tol_mm);
}

std::vector<Hole> detect_holes(const Model& model, const Setup& setup, double tol_mm) {
  return occt::detect_holes(model, setup, tol_mm);
}

std::vector<Polygon> offset_inset(const Polygon& poly, double radius_mm) {
  return geom2d::offset_inset(poly, radius_mm);
}

std::vector<Polygon> offset_outset(const Polygon& poly, double radius_mm) {
  return geom2d::offset_outset(poly, radius_mm);
}

Paths plan_pocket(const PlanarFace& face, const Tool& tool, double step_over_mm, double step_down_mm,
                  double safe_z_mm) {
  return algo::plan_pocket(face, tool, step_over_mm, step_down_mm, safe_z_mm);
}

Paths plan_profile(const Polygon& boundary, const Tool& tool, double total_depth_mm, double step_down_mm,
                   double safe_z_mm) {
  return algo::plan_profile(boundary, tool, total_depth_mm, step_down_mm, safe_z_mm);
}

Paths plan_drill(const std::vector<Hole>& holes, const Tool& tool, double peck_mm, double safe_z_mm) {
  return algo::plan_drill(holes, tool, peck_mm, safe_z_mm);
}

Paths plan_bore_helical(const Hole& hole, const Tool& tool, double step_down_mm, double safe_z_mm) {
  return algo::plan_bore_helical(hole, tool, step_down_mm, safe_z_mm);
}

std::string post_gcode(const Paths& paths, const PostConfig& cfg) {
  return algo::post_gcode(paths, cfg);
}

std::string create_stock(double minx, double miny, double maxx, double maxy, double pitch_mm) {
  (void)minx;
  (void)miny;
  (void)maxx;
  (void)maxy;
  (void)pitch_mm;
  return "";
}

Paths link_keepdown(const Paths& paths, double, double) {
  return paths;
}

Paths fit_arcs(const Paths& paths, double) {
  return paths;
}

}  // namespace millui::native
