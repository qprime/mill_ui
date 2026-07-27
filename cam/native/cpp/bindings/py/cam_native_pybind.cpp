#include "millui/native/algo/plan_2d.hpp"
#include "millui/native/algo/post_gcode.hpp"
#include "millui/native/types.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cmath>
#include <optional>
#include <stdexcept>

namespace py = pybind11;
using namespace millui::native;

namespace {

bool has(double v) {
  return !std::isnan(v);
}

Vec2 vec2_from_py(const py::sequence& seq) {
  if (seq.size() != 2) {
    throw std::invalid_argument("Vec2 requires 2 elements");
  }
  return Vec2{seq[0].cast<double>(), seq[1].cast<double>()};
}

Polygon polygon_from_py(const py::sequence& seq) {
  Polygon poly;
  poly.reserve(seq.size());
  for (const auto& item : seq) {
    py::sequence pair = py::reinterpret_borrow<py::sequence>(item);
    poly.emplace_back(vec2_from_py(pair));
  }
  return poly;
}

Tool tool_from_py(const py::object& obj) {
  Tool tool;
  tool.diameter = obj.attr("diameter").cast<double>();
  tool.rpm = obj.attr("rpm").cast<double>();
  tool.feed_xy = obj.attr("feed_xy").cast<double>();
  tool.feed_z = obj.attr("feed_z").cast<double>();
  tool.kind = py::str(obj.attr("kind"));
  return tool;
}

Hole hole_from_dict(const py::dict& d) {
  Hole hole;
  hole.x = d["x"].cast<double>();
  hole.y = d["y"].cast<double>();
  hole.diameter = d["diameter"].cast<double>();
  hole.depth = d["depth"].cast<double>();
  return hole;
}

PlanarFace face_from_dict(const py::dict& d) {
  PlanarFace face;
  face.z = d.contains("z") ? d["z"].cast<double>() : 0.0;
  face.depth = d.contains("depth") ? d["depth"].cast<double>() : 0.0;
  face.safe_z = d.contains("safe_z") ? d["safe_z"].cast<double>() : 5.0;
  face.outer = polygon_from_py(py::reinterpret_borrow<py::sequence>(d["outer"]));
  if (d.contains("holes")) {
    py::sequence holes_seq = py::reinterpret_borrow<py::sequence>(d["holes"]);
    for (const auto& item : holes_seq) {
      face.holes.push_back(polygon_from_py(py::reinterpret_borrow<py::sequence>(item)));
    }
  }
  return face;
}

py::dict move_to_dict(const PathMove& mv) {
  py::dict d;
  d["kind"] = mv.kind;
  d["x"] = has(mv.x) ? py::cast(mv.x) : py::none();
  d["y"] = has(mv.y) ? py::cast(mv.y) : py::none();
  d["z"] = has(mv.z) ? py::cast(mv.z) : py::none();
  d["feed"] = has(mv.feed) ? py::cast(mv.feed) : py::none();
  d["rpm"] = has(mv.rpm) ? py::cast(mv.rpm) : py::none();
  d["seconds"] = has(mv.seconds) ? py::cast(mv.seconds) : py::none();
  if (!mv.text.empty()) {
    d["text"] = mv.text;
  } else {
    d["text"] = py::none();
  }
  return d;
}

py::list paths_to_flat_list(const Paths& paths) {
  py::list out;
  for (const auto& path : paths) {
    for (const auto& mv : path) {
      out.append(move_to_dict(mv));
    }
  }
  return out;
}

Paths paths_from_flat_list(const py::sequence& seq) {
  Paths paths(1);
  Path& path = paths.front();
  path.reserve(seq.size());
  for (const auto& item : seq) {
    py::dict d = py::reinterpret_borrow<py::dict>(item);
    PathMove mv;
    mv.kind = py::str(d["kind"]);
    if (d.contains("x") && !d["x"].is_none()) mv.x = d["x"].cast<double>();
    if (d.contains("y") && !d["y"].is_none()) mv.y = d["y"].cast<double>();
    if (d.contains("z") && !d["z"].is_none()) mv.z = d["z"].cast<double>();
    if (d.contains("feed") && !d["feed"].is_none()) mv.feed = d["feed"].cast<double>();
    if (d.contains("rpm") && !d["rpm"].is_none()) mv.rpm = d["rpm"].cast<double>();
    if (d.contains("seconds") && !d["seconds"].is_none()) mv.seconds = d["seconds"].cast<double>();
    if (d.contains("text") && !d["text"].is_none()) mv.text = py::str(d["text"]);
    path.push_back(std::move(mv));
  }
  return paths;
}

PostConfig post_cfg_from_dict(const py::dict& d) {
  PostConfig cfg;
  cfg.unit = d.contains("unit") ? py::str(d["unit"]) : "mm";
  cfg.safe_z = d.contains("safe_z") ? d["safe_z"].cast<double>() : 5.0;
  cfg.prec = d.contains("prec") ? d["prec"].cast<int>() : 3;
  if (d.contains("header") && !d["header"].is_none()) {
    py::sequence seq = py::reinterpret_borrow<py::sequence>(d["header"]);
    for (const auto& item : seq) {
      cfg.header.emplace_back(py::str(item));
    }
  }
  if (d.contains("footer") && !d["footer"].is_none()) {
    py::sequence seq = py::reinterpret_borrow<py::sequence>(d["footer"]);
    for (const auto& item : seq) {
      cfg.footer.emplace_back(py::str(item));
    }
  }
  return cfg;
}

}  // namespace

PYBIND11_MODULE(_native, m) {
  m.doc() = "Native CAM core bindings";

  m.def("plan_pocket", [](const py::dict& face_dict, const py::object& tool_obj, double step_over_mm,
                           std::optional<double> step_down_mm, double ramp_angle_deg,
                           const std::string& strategy) {
    PlanarFace face = face_from_dict(face_dict);
    Tool tool = tool_from_py(tool_obj);
    double step_down = step_down_mm.value_or(0.0);
    auto strat = (strategy == "raster") ? PocketStrategy::Raster : PocketStrategy::Spiral;
    return paths_to_flat_list(algo::plan_pocket(face, tool, step_over_mm, step_down, face.safe_z, ramp_angle_deg, strat));
  }, py::arg("face"), py::arg("tool"), py::arg("step_over_mm"),
     py::arg("step_down_mm") = py::none(), py::arg("ramp_angle_deg") = 0.0,
     py::arg("strategy") = "spiral");

  m.def("plan_profile", [](const py::sequence& boundary, const py::object& tool_obj, double total_depth_mm,
                            double step_down_mm, double safe_z_mm, double ramp_angle_deg) {
    Polygon poly = polygon_from_py(boundary);
    Tool tool = tool_from_py(tool_obj);
    return paths_to_flat_list(algo::plan_profile(poly, tool, total_depth_mm, step_down_mm, safe_z_mm, ramp_angle_deg));
  }, py::arg("boundary"), py::arg("tool"), py::arg("total_depth_mm"),
     py::arg("step_down_mm"), py::arg("safe_z_mm"), py::arg("ramp_angle_deg") = 0.0);

  m.def("plan_drill", [](const py::sequence& holes_seq, const py::object& tool_obj, double peck_mm,
                           double safe_z_mm) {
    std::vector<Hole> holes;
    holes.reserve(holes_seq.size());
    for (const auto& item : holes_seq) {
      holes.push_back(hole_from_dict(py::reinterpret_borrow<py::dict>(item)));
    }
    Tool tool = tool_from_py(tool_obj);
    return paths_to_flat_list(algo::plan_drill(holes, tool, peck_mm, safe_z_mm));
  }, py::arg("holes"), py::arg("tool"), py::arg("peck_mm"), py::arg("safe_z_mm"));

  m.def("plan_bore_helical", [](const py::dict& hole_dict, const py::object& tool_obj, double step_down_mm,
                                  double safe_z_mm) {
    Hole hole = hole_from_dict(hole_dict);
    Tool tool = tool_from_py(tool_obj);
    return paths_to_flat_list(algo::plan_bore_helical(hole, tool, step_down_mm, safe_z_mm));
  }, py::arg("hole"), py::arg("tool"), py::arg("step_down_mm"), py::arg("safe_z_mm"));

  m.def("post_gcode", [](const py::sequence& paths_seq, const py::dict& cfg_dict) {
    Paths paths = paths_from_flat_list(paths_seq);
    PostConfig cfg = post_cfg_from_dict(cfg_dict);
    return algo::post_gcode(paths, cfg);
  }, py::arg("paths"), py::arg("cfg"));
}
