// SPDX-License-Identifier: UNLICENSED
#include "millui/native/algo/mandelbrot.hpp"

#include <algorithm>
#include <cmath>
#include <future>
#include <thread>

namespace millui::native::algo {

namespace {

inline bool in_set(double cx, double cy, int iterations, double escape_sq) {
  double zr = 0.0, zi = 0.0;
  for (int i = 0; i < iterations; ++i) {
    const double zr2 = zr * zr;
    const double zi2 = zi * zi;
    if (zr2 + zi2 > escape_sq) return false;
    const double two_zr_zi = 2.0 * zr * zi;
    zr = zr2 - zi2 + cx;
    zi = two_zr_zi + cy;
  }
  return true;
}

// Marching squares edge interpolation (simple midpoint for speed)
inline std::pair<double,double> interp(double x0, double y0, double x1, double y1) {
  return {(x0 + x1) * 0.5, (y0 + y1) * 0.5};
}

// Trace contours using a basic marching squares pass that emits small segments per cell edge.
// For large-format non-zoomed outlines this yields good visual quality; callers can simplify later if needed.
static void extract_outlines(const std::vector<uint8_t>& mask, int nx, int ny,
                             double w_mm, double h_mm, std::vector<Polygon>& out) {
  // cell size
  const double cell_w = w_mm / static_cast<double>(nx);
  const double cell_h = h_mm / static_cast<double>(ny);
  // panel origin at center; convert cell-local coords to panel mm coords
  auto to_panel = [&](double cx, double cy) {
    // cx, cy are in [0,w_mm]x[0,h_mm] with 0,0 at bottom-left; convert to center origin
    return Vec2{cx - 0.5 * w_mm, cy - 0.5 * h_mm};
  };

  // For simplicity, collect segments per cell and join per-row; this is not a topological stitcher,
  // but is sufficient to produce closed polylines visually along the boundary at this resolution.
  // We emit small 2-vertex segments that downstream engraving can follow; consumer may arc-fit later.
  for (int j = 0; j < ny - 1; ++j) {
    for (int i = 0; i < nx - 1; ++i) {
      const int idx = j * nx + i;
      const bool a = mask[idx] != 0;
      const bool b = mask[idx + 1] != 0;
      const bool c = mask[idx + nx] != 0;
      const bool d = mask[idx + nx + 1] != 0;
      const int code = (a ? 1 : 0) | (b ? 2 : 0) | (c ? 4 : 0) | (d ? 8 : 0);
      if (code == 0 || code == 15) continue; // fully out/in

      const double x0 = (i + 0) * cell_w;
      const double y0 = (j + 0) * cell_h;
      const double x1 = (i + 1) * cell_w;
      const double y1 = (j + 1) * cell_h;

      // interpolate midpoints along edges
      const auto e_bottom = to_panel(interp(x0, y0, x1, y0).first, interp(x0, y0, x1, y0).second);
      const auto e_top    = to_panel(interp(x0, y1, x1, y1).first, interp(x0, y1, x1, y1).second);
      const auto e_left   = to_panel(interp(x0, y0, x0, y1).first, interp(x0, y0, x0, y1).second);
      const auto e_right  = to_panel(interp(x1, y0, x1, y1).first, interp(x1, y0, x1, y1).second);

      // Cases emit one or two segments; we push tiny polylines (2-pt)
      auto push_seg = [&](const Vec2& s, const Vec2& t) {
        Polygon poly; poly.reserve(2); poly.push_back(s); poly.push_back(t); out.push_back(std::move(poly));
      };

      switch (code) {
        case 1:  case 14: push_seg(e_left, e_bottom); break;
        case 2:  case 13: push_seg(e_bottom, e_right); break;
        case 3:  case 12: push_seg(e_left, e_right); break;
        case 4:  case 11: push_seg(e_top, e_left); break;
        case 5:             push_seg(e_top, e_bottom); break;
        case 6:  case 9:  push_seg(e_top, e_right); break;
        case 7:  case 8:  push_seg(e_top, e_bottom); break;
        case 10:          push_seg(e_left, e_right); break;
        default: break;
      }
    }
  }
}

} // namespace

MandelbrotResult mandelbrot_outline_fill(
    double width_mm, double height_mm, int res_x, int res_y,
    int iterations, double escape_radius,
    double real_min, double real_max, double imag_min, double imag_max) {
  MandelbrotResult result;
  if (width_mm <= 0.0 || height_mm <= 0.0 || res_x < 4 || res_y < 4) {
    return result;
  }

  const int nx = res_x;
  const int ny = res_y;
  const double rx = (real_max - real_min) / static_cast<double>(nx);
  const double ry = (imag_max - imag_min) / static_cast<double>(ny);
  const double cell_w = width_mm / static_cast<double>(nx);
  const double cell_h = height_mm / static_cast<double>(ny);
  const double esc_sq = escape_radius * escape_radius;

  std::vector<uint8_t> mask(static_cast<size_t>(nx) * ny, 0);

  // Parallelise rows with a simple async pool
  const unsigned threads = std::max(1u, std::thread::hardware_concurrency());
  const int rows_per_chunk = std::max(1, ny / static_cast<int>(threads));
  std::vector<std::future<void>> futs;
  futs.reserve(threads);
  for (unsigned t = 0; t < threads; ++t) {
    const int start = static_cast<int>(t) * rows_per_chunk;
    if (start >= ny) break;
    const int end = (t + 1 == threads) ? ny : std::min(ny, start + rows_per_chunk);
    futs.emplace_back(std::async(std::launch::async, [&, start, end]() {
      for (int j = start; j < end; ++j) {
        const double imag = imag_max - (j + 0.5) * ry;
        for (int i = 0; i < nx; ++i) {
          const double real = real_min + (i + 0.5) * rx;
          const bool inside = in_set(real, imag, iterations, esc_sq);
          mask[static_cast<size_t>(j) * nx + i] = inside ? 1 : 0;
        }
      }
    }));
  }
  for (auto& f : futs) f.get();

  // Extract fill spans per row (merge adjacent 'inside' cells)
  result.spans.reserve(static_cast<size_t>(ny));
  for (int j = 0; j < ny; ++j) {
    int i = 0;
    while (i < nx) {
      while (i < nx && mask[static_cast<size_t>(j) * nx + i] == 0) ++i;
      if (i >= nx) break;
      const int run_start = i;
      while (i < nx && mask[static_cast<size_t>(j) * nx + i] != 0) ++i;
      const int run_end = i; // exclusive
      const double x0 = (run_start) * cell_w - 0.5 * width_mm;
      const double x1 = (run_end) * cell_w - 0.5 * width_mm;
      const double yb = (j) * cell_h - 0.5 * height_mm; // baseline at bottom of cell row
      result.spans.push_back(MandelbrotSpan{yb, x0, x1, cell_h});
    }
  }

  // Extract outline segments via marching squares
  extract_outlines(mask, nx, ny, width_mm, height_mm, result.outlines);

  return result;
}

}  // namespace millui::native::algo
