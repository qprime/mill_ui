#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cmath>
#include <optional>
#include <stdexcept>
#include <string>
#include <variant>

#include "millui/native/algo/format.hpp"
#include "millui/native/algo/plan_2d.hpp"
#include "millui/native/algo/post_gcode.hpp"
#include "millui/native/types.hpp"

namespace py = pybind11;
using namespace millui::native;

namespace {

py::object opt_to_py(std::optional<double> v) { return v ? py::cast(*v) : py::none(); }

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
    face.depth = d.contains("depth") ? d["depth"].cast<double>() : 0.0;
    face.safe_z = d.contains("safe_z") ? d["safe_z"].cast<double>() : 5.0;
    face.outer = polygon_from_py(py::reinterpret_borrow<py::sequence>(d["outer"]));
    return face;
}

py::dict move_to_dict(const Move& mv) {
    py::dict d;
    d["x"] = py::none();
    d["y"] = py::none();
    d["z"] = py::none();
    d["feed"] = py::none();
    d["rpm"] = py::none();
    d["seconds"] = py::none();
    d["text"] = py::none();
    std::visit(overloaded{
                   [&](const Comment& c) {
                       d["kind"] = "comment";
                       if (!c.text.empty()) {
                           d["text"] = c.text;
                       }
                   },
                   [&](const SetRpm& s) {
                       d["kind"] = "set_rpm";
                       d["rpm"] = s.rpm;
                   },
                   [&](const SetFeed& s) {
                       d["kind"] = "set_feed";
                       d["feed"] = s.feed;
                   },
                   [&](const Rapid& r) {
                       d["kind"] = "rapid";
                       d["x"] = opt_to_py(r.x);
                       d["y"] = opt_to_py(r.y);
                       d["z"] = opt_to_py(r.z);
                   },
                   [&](const Cut& c) {
                       d["kind"] = "cut";
                       d["x"] = opt_to_py(c.x);
                       d["y"] = opt_to_py(c.y);
                       d["z"] = opt_to_py(c.z);
                       d["feed"] = opt_to_py(c.feed);
                   },
                   [&](const Retract& r) {
                       d["kind"] = "retract";
                       d["z"] = r.z;
                   },
                   [&](const Dwell& dw) {
                       d["kind"] = "dwell";
                       d["seconds"] = dw.seconds;
                   },
               },
               mv);
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

std::optional<double> opt_field(const py::dict& d, const char* key) {
    if (d.contains(key) && !d[key].is_none()) {
        return d[key].cast<double>();
    }
    return std::nullopt;
}

Paths paths_from_flat_list(const py::sequence& seq, double safe_z) {
    Paths paths(1);
    Path& path = paths.front();
    path.reserve(seq.size());
    for (const auto& item : seq) {
        py::dict d = py::reinterpret_borrow<py::dict>(item);
        const std::string kind = py::str(d["kind"]);
        if (kind == "comment") {
            std::string text;
            if (d.contains("text") && !d["text"].is_none()) {
                text = py::str(d["text"]);
            }
            path.push_back(Comment{std::move(text)});
        } else if (kind == "set_rpm") {
            path.push_back(SetRpm{opt_field(d, "rpm").value_or(0.0)});
        } else if (kind == "set_feed") {
            path.push_back(SetFeed{opt_field(d, "feed").value_or(0.0)});
        } else if (kind == "rapid") {
            path.push_back(Rapid{opt_field(d, "x"), opt_field(d, "y"), opt_field(d, "z")});
        } else if (kind == "cut") {
            path.push_back(
                Cut{opt_field(d, "x"), opt_field(d, "y"), opt_field(d, "z"), opt_field(d, "feed")});
        } else if (kind == "retract") {
            path.push_back(Retract{opt_field(d, "z").value_or(safe_z)});
        } else if (kind == "dwell") {
            path.push_back(Dwell{opt_field(d, "seconds").value_or(0.0)});
        } else {
            throw std::invalid_argument(
                "post_gcode: move.kind must be one of "
                "comment|set_rpm|set_feed|rapid|cut|retract|dwell, got '" +
                kind + "'");
        }
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

double checked_scalar(double v, double min, const char* fn, const char* field) {
    if (!std::isfinite(v) || v < min) {
        throw std::invalid_argument(std::string(fn) + ": " + field + " must be finite and >= " +
                                    algo::format_compact(min) + ", got " + algo::format_compact(v));
    }
    return v;
}

double checked_step_scalar(double v, const char* fn, const char* field) {
    if (!std::isfinite(v) || v < 0.0 || (v > 0.0 && v < algo::kMinStepDownMm)) {
        throw std::invalid_argument(
            std::string(fn) + ": " + field + " must be finite and either 0 or >= " +
            algo::format_compact(algo::kMinStepDownMm) + ", got " + algo::format_compact(v));
    }
    return v;
}

PocketStrategy strategy_from_string(const std::string& strategy) {
    if (strategy == "raster") {
        return PocketStrategy::Raster;
    }
    if (strategy == "spiral") {
        return PocketStrategy::Spiral;
    }
    throw std::invalid_argument("plan_pocket: strategy must be one of raster|spiral, got '" +
                                strategy + "'");
}

}  // namespace

PYBIND11_MODULE(_native, m) {
    m.doc() = "Native CAM core bindings";

    m.def(
        "plan_pocket",
        [](const py::dict& face_dict, const py::object& tool_obj, double step_over_mm,
           std::optional<double> step_down_mm, double ramp_angle_deg, const std::string& strategy) {
            PlanarFace face = face_from_dict(face_dict);
            Tool tool = tool_from_py(tool_obj);
            checked_scalar(step_over_mm, 0.0, "plan_pocket", "step_over_mm");
            double step_down = step_down_mm ? checked_scalar(*step_down_mm, algo::kMinStepDownMm,
                                                             "plan_pocket", "step_down_mm")
                                            : 0.0;
            PocketStrategy strat = strategy_from_string(strategy);
            return paths_to_flat_list(algo::plan_pocket(face, tool, step_over_mm, step_down,
                                                        face.safe_z, ramp_angle_deg, strat));
        },
        py::arg("face"), py::arg("tool"), py::arg("step_over_mm"),
        py::arg("step_down_mm") = py::none(), py::arg("ramp_angle_deg") = 0.0,
        py::arg("strategy") = "spiral");

    m.def(
        "plan_profile",
        [](const py::sequence& boundary, const py::object& tool_obj, double total_depth_mm,
           double step_down_mm, double safe_z_mm, double ramp_angle_deg) {
            Polygon poly = polygon_from_py(boundary);
            Tool tool = tool_from_py(tool_obj);
            checked_step_scalar(step_down_mm, "plan_profile", "step_down_mm");
            return paths_to_flat_list(algo::plan_profile(poly, tool, total_depth_mm, step_down_mm,
                                                         safe_z_mm, ramp_angle_deg));
        },
        py::arg("boundary"), py::arg("tool"), py::arg("total_depth_mm"), py::arg("step_down_mm"),
        py::arg("safe_z_mm"), py::arg("ramp_angle_deg") = 0.0);

    m.def(
        "plan_drill",
        [](const py::sequence& holes_seq, const py::object& tool_obj, double peck_mm,
           double safe_z_mm) {
            std::vector<Hole> holes;
            holes.reserve(holes_seq.size());
            for (const auto& item : holes_seq) {
                holes.push_back(hole_from_dict(py::reinterpret_borrow<py::dict>(item)));
            }
            Tool tool = tool_from_py(tool_obj);
            checked_step_scalar(peck_mm, "plan_drill", "peck_mm");
            return paths_to_flat_list(algo::plan_drill(holes, tool, peck_mm, safe_z_mm));
        },
        py::arg("holes"), py::arg("tool"), py::arg("peck_mm"), py::arg("safe_z_mm"));

    m.def(
        "plan_bore_helical",
        [](const py::dict& hole_dict, const py::object& tool_obj, double step_down_mm,
           double safe_z_mm) {
            Hole hole = hole_from_dict(hole_dict);
            Tool tool = tool_from_py(tool_obj);
            checked_step_scalar(step_down_mm, "plan_bore_helical", "step_down_mm");
            return paths_to_flat_list(algo::plan_bore_helical(hole, tool, step_down_mm, safe_z_mm));
        },
        py::arg("hole"), py::arg("tool"), py::arg("step_down_mm"), py::arg("safe_z_mm"));

    m.def(
        "post_gcode",
        [](const py::sequence& paths_seq, const py::dict& cfg_dict) {
            PostConfig cfg = post_cfg_from_dict(cfg_dict);
            Paths paths = paths_from_flat_list(paths_seq, cfg.safe_z);
            return algo::post_gcode(paths, cfg);
        },
        py::arg("paths"), py::arg("cfg"));
}
