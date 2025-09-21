#pragma once

#include <vector>

#include "millui/native/facade.hpp"

namespace millui::native::geom2d {

std::vector<Polygon> offset_inset(const Polygon& poly, double radius_mm);
std::vector<Polygon> offset_outset(const Polygon& poly, double radius_mm);

}  // namespace millui::native::geom2d
