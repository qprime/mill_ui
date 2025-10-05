#include "millui/native/algo/mandelbrot.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;
using millui::native::Vec2;
using millui::native::Polygon;
using millui::native::algo::MandelbrotResult;
using millui::native::algo::MandelbrotSpan;

namespace {

py::list polygon_to_py(const Polygon& poly) {
  py::list out;
  for (const auto& pt : poly) out.append(py::make_tuple(pt.x, pt.y));
  return out;
}

} // namespace

void bind_mandelbrot(py::module_& m) {
  m.def("mandelbrot_outline_fill",
        [](double width_mm, double height_mm, int res_x, int res_y,
           int iterations, double escape_radius,
           double real_min, double real_max, double imag_min, double imag_max) {
          MandelbrotResult r = millui::native::algo::mandelbrot_outline_fill(
              width_mm, height_mm, res_x, res_y, iterations, escape_radius,
              real_min, real_max, imag_min, imag_max);

          py::dict out;
          // outlines
          py::list polys;
          for (const auto& p : r.outlines) polys.append(polygon_to_py(p));
          out["polylines"] = std::move(polys);
          // spans
          py::list spans;
          for (const MandelbrotSpan& s : r.spans) {
            py::dict d;
            d["y"] = s.y;
            d["x0"] = s.x0;
            d["x1"] = s.x1;
            d["h"] = s.h;
            spans.append(std::move(d));
          }
          out["spans"] = std::move(spans);
          return out;
        },
        R"doc(
Return dict with:
  polylines: list[list[(x,y)]]  — boundary segments in panel mm coords (origin center)
  spans:     list[{x0,x1,y,h}] — horizontal fill spans per row (panel mm coords)
)doc");
}

// Register into the existing module init by referencing a weak symbol emitted by cam_native_pybind.cpp
extern "C" void millui_native_register_extra(py::module_&);
extern "C" void millui_native_register_extra(py::module_& m) {
  bind_mandelbrot(m);
}
