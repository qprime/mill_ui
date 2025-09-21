#include "millui/native/geom2d/clipper2_wrap.hpp"

#include <vector>

namespace millui::native::geom2d {

std::vector<Polygon> offset_inset(const Polygon& poly, double) {
  return {poly};
}

std::vector<Polygon> offset_outset(const Polygon& poly, double) {
  return {poly};
}

}  // namespace millui::native::geom2d
