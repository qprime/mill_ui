#pragma once

#include <memory>
#include <string>
#include <vector>

#include "millui/native/facade.hpp"

namespace millui::native::occt {

struct StepResult {
  std::unique_ptr<Model> model;
  std::string warning;
};

StepResult load_step(const std::string& path);
std::unique_ptr<Setup> make_setup(const Model& model, double tol_mm);
std::vector<PlanarFace> detect_planar(const Model& model, const Setup& setup, double tol_mm);
std::vector<Hole> detect_holes(const Model& model, const Setup& setup, double tol_mm);

}  // namespace millui::native::occt
