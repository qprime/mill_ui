// SPDX-License-Identifier: UNLICENSED
#pragma once

#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

#include "millui/native/facade.hpp"

namespace millui::native::algo {

struct MandelbrotSpan {
  // Continuous horizontal run inside the set at a given row in panel-mm coords
  double y;    // row baseline (bottom of the cell) in mm, panel origin (0,0) at center
  double x0;   // left edge in mm
  double x1;   // right edge in mm
  double h;    // span height in mm (cell height)
};

struct MandelbrotResult {
  std::vector<Polygon> outlines;   // one or more closed polylines in mm coords
  std::vector<MandelbrotSpan> spans; // interior fill spans for pocketing
};

// Compute a binary membership grid for the Mandelbrot set and extract:
//  - closed outlines via marching squares
//  - horizontal fill spans per row (merged)
// Panel space: width_mm x height_mm, origin at center (0,0)
MandelbrotResult mandelbrot_outline_fill(
    double width_mm,
    double height_mm,
    int res_x,
    int res_y,
    int iterations,
    double escape_radius,
    double real_min,
    double real_max,
    double imag_min,
    double imag_max);

}  // namespace millui::native::algo

