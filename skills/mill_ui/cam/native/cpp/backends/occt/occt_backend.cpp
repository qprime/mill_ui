#include "millui/native/backends/occt/occt_backend.hpp"
#include "millui/native/facade.hpp"

#include <filesystem>
#include <sstream>

namespace millui::native::occt {

StepResult load_step(const std::string& path) {
  StepResult result;
  namespace fs = std::filesystem;
  fs::path p(path);
  if (!fs::exists(p)) {
    std::ostringstream oss;
    oss << "STEP path not found: " << path;
    throw std::runtime_error(oss.str());
  }

  auto model = std::make_unique<Model>();
  model->source_path = fs::absolute(p).string();
  result.model = std::move(model);
  return result;
}

std::unique_ptr<Setup> make_setup(const Model&, double tol_mm) {
  auto setup = std::make_unique<Setup>();
  setup->tol_mm = tol_mm;
  return setup;
}

std::vector<PlanarFace> detect_planar(const Model&, const Setup&, double) {
  return {};
}

std::vector<Hole> detect_holes(const Model&, const Setup&, double) {
  return {};
}

}  // namespace millui::native::occt
