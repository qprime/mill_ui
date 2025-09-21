#include "millui/native/facade.hpp"

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

py::list polygon_to_py(const Polygon& poly) {
  py::list out;
  for (const auto& pt : poly) {
    out.append(py::make_tuple(pt.x, pt.y));
  }
  return out;
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

py::dict face_to_dict(const PlanarFace& face) {
  py::dict d;
  d["z"] = face.z;
  d["depth"] = face.depth;
  d["safe_z"] = face.safe_z;
  d["outer"] = polygon_to_py(face.outer);
  py::list holes;
  for (const auto& hole : face.holes) {
    holes.append(polygon_to_py(hole));
  }
  d["holes"] = std::move(holes);
  return d;
}

py::dict hole_to_dict(const Hole& hole) {
  py::dict d;
  d["x"] = hole.x;
  d["y"] = hole.y;
  d["diameter"] = hole.diameter;
  d["depth"] = hole.depth;
  return d;
}

}  // namespace

PYBIND11_MODULE(_native, m) {
  m.doc() = "Native CAM core bindings";

  py::class_<Model>(m, "Model")
      .def(py::init<>())
      .def_readwrite("source_path", &Model::source_path);

  py::class_<Setup>(m, "Setup")
      .def(py::init<>())
      .def_readwrite("tol_mm", &Setup::tol_mm)
      .def_readwrite("safe_z", &Setup::safe_z);

  m.def("load_step", [](const std::string& path) {
    return load_step(path);
  });

  m.def("make_setup", [](const Model& model, double tol_mm) {
    return make_setup(model, tol_mm);
  });

  m.def("detect_planar", [](const Model& model, const Setup& setup, double tol_mm) {
    auto faces = detect_planar(model, setup, tol_mm);
    py::list out;
    for (const auto& face : faces) {
      out.append(face_to_dict(face));
    }
    return out;
  });

  m.def("detect_holes", [](const Model& model, const Setup& setup, double tol_mm) {
    auto holes = detect_holes(model, setup, tol_mm);
    py::list out;
    for (const auto& hole : holes) {
      out.append(hole_to_dict(hole));
    }
    return out;
  });

  m.def("offset_inset", [](const py::sequence& poly, double radius_mm) {
    auto polys = millui::native::offset_inset(polygon_from_py(poly), radius_mm);
    py::list out;
    for (const auto& p : polys) {
      out.append(polygon_to_py(p));
    }
    return out;
  });

  m.def("offset_outset", [](const py::sequence& poly, double radius_mm) {
    auto polys = millui::native::offset_outset(polygon_from_py(poly), radius_mm);
    py::list out;
    for (const auto& p : polys) {
      out.append(polygon_to_py(p));
    }
    return out;
  });

  m.def("plan_pocket", [](const py::dict& face_dict, const py::object& tool_obj, double step_over_mm,
                           std::optional<double> step_down_mm) {
    PlanarFace face = face_from_dict(face_dict);
    Tool tool = tool_from_py(tool_obj);
    double step_down = step_down_mm.value_or(0.0);
    return paths_to_flat_list(millui::native::plan_pocket(face, tool, step_over_mm, step_down, face.safe_z));
  });

  m.def("plan_profile", [](const py::sequence& boundary, const py::object& tool_obj, double total_depth_mm,
                            double step_down_mm, double safe_z_mm) {
    Polygon poly = polygon_from_py(boundary);
    Tool tool = tool_from_py(tool_obj);
    return paths_to_flat_list(millui::native::plan_profile(poly, tool, total_depth_mm, step_down_mm, safe_z_mm));
  });

  m.def("plan_drill", [](const py::sequence& holes_seq, const py::object& tool_obj, double peck_mm,
                           double safe_z_mm) {
    std::vector<Hole> holes;
    holes.reserve(holes_seq.size());
    for (const auto& item : holes_seq) {
      holes.push_back(hole_from_dict(py::reinterpret_borrow<py::dict>(item)));
    }
    Tool tool = tool_from_py(tool_obj);
    return paths_to_flat_list(millui::native::plan_drill(holes, tool, peck_mm, safe_z_mm));
  });

  m.def("plan_bore_helical", [](const py::dict& hole_dict, const py::object& tool_obj, double step_down_mm,
                                  double safe_z_mm) {
    Hole hole = hole_from_dict(hole_dict);
    Tool tool = tool_from_py(tool_obj);
    return paths_to_flat_list(millui::native::plan_bore_helical(hole, tool, step_down_mm, safe_z_mm));
  });

  m.def("post_gcode", [](const py::sequence& paths_seq, const py::dict& cfg_dict) {
    Paths paths = paths_from_flat_list(paths_seq);
    PostConfig cfg = post_cfg_from_dict(cfg_dict);
    return millui::native::post_gcode(paths, cfg);
  });

  m.def("create_stock", &millui::native::create_stock);
  m.def("link_keepdown", [](const py::sequence& seq, double safe_z, double min_clearance) {
    Paths paths = paths_from_flat_list(seq);
    Paths linked = millui::native::link_keepdown(paths, safe_z, min_clearance);
    return paths_to_flat_list(linked);
  });
  m.def("fit_arcs", [](const py::sequence& seq, double tol_mm) {
    Paths paths = paths_from_flat_list(seq);
    Paths fitted = millui::native::fit_arcs(paths, tol_mm);
    return paths_to_flat_list(fitted);
  });
}
