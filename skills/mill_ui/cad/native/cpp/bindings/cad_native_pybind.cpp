#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include <BRepAlgoAPI_Cut.hxx>
#include <BRep_Builder.hxx>
#include <BRepMesh_IncrementalMesh.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <ShapeFix_Shape.hxx>
#include <StlAPI_Writer.hxx>
#include <STEPControl_Writer.hxx>
#include <IFSelect_ReturnStatus.hxx>
#include <TopoDS_Compound.hxx>
#include <TopoDS_Shape.hxx>
#include <gp_Ax2.hxx>
#include <gp_Dir.hxx>
#include <gp_Pnt.hxx>

namespace py = pybind11;

namespace {

using ShapeList = std::vector<py::dict>;

struct SheetSpec {
  double width = 0.0;
  double height = 0.0;
  double thickness = 0.0;
};

enum class ShapeKind { Rect, Circle, Polyline, Other };

enum class FeatureKind { Profile, Pocket, Engrave, Other };

struct ShapeInput {
  std::string id;
  ShapeKind shape_kind = ShapeKind::Other;
  FeatureKind feature_kind = FeatureKind::Other;
  double width = 0.0;
  double height = 0.0;
  double diameter = 0.0;
  double center_x = 0.0;
  double center_y = 0.0;
  double depth = 0.0;
  bool through = false;
};

std::string to_lower(std::string s) {
  std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return std::tolower(c); });
  return s;
}

py::str py_str(const char *value) {
  return py::str(value);
}

bool dict_contains(const py::dict &dict, const char *key) {
  return dict.contains(py::str(key));
}

py::object dict_get(const py::dict &dict, const char *key) {
  if (dict_contains(dict, key)) {
    return dict[py::str(key)];
  }
  return py::none();
}

double as_double(const py::object &obj, double fallback = 0.0) {
  if (obj.is_none()) {
    return fallback;
  }
  try {
    return obj.cast<double>();
  } catch (const py::cast_error &) {
    return fallback;
  }
}

ShapeKind parse_shape_kind(const py::dict &shape_dict) {
  if (!dict_contains(shape_dict, "type")) {
    return ShapeKind::Other;
  }
  const std::string type = to_lower(py::str(shape_dict[py_str("type")]));
  if (type == "rect") {
    return ShapeKind::Rect;
  }
  if (type == "circle") {
    return ShapeKind::Circle;
  }
  if (type == "polyline") {
    return ShapeKind::Polyline;
  }
  return ShapeKind::Other;
}

FeatureKind parse_feature_kind(const py::dict &feature_dict) {
  if (!dict_contains(feature_dict, "type")) {
    return FeatureKind::Other;
  }
  const std::string type = to_lower(py::str(feature_dict[py_str("type")]));
  if (type == "profile" || type == "slot") {
    return FeatureKind::Profile;
  }
  if (type == "pocket") {
    return FeatureKind::Pocket;
  }
  if (type == "engrave") {
    return FeatureKind::Engrave;
  }
  return FeatureKind::Other;
}

std::pair<double, double> parse_center_xy(const py::dict &shape_dict) {
  if (!dict_contains(shape_dict, "placement")) {
    return {0.0, 0.0};
  }
  const py::dict placement = shape_dict[py_str("placement")].cast<py::dict>();
  if (!dict_contains(placement, "center_xy_mm")) {
    return {0.0, 0.0};
  }
  try {
    const auto coords = placement[py_str("center_xy_mm")].cast<std::vector<double>>();
    if (coords.size() == 2) {
      return {coords[0], coords[1]};
    }
  } catch (const py::cast_error &) {
  }
  return {0.0, 0.0};
}

double feature_depth_mm(const py::dict &feature_dict, double sheet_thickness) {
  if (dict_contains(feature_dict, "depth_mm")) {
    return as_double(feature_dict[py_str("depth_mm")], 0.0);
  }
  if (dict_contains(feature_dict, "depth")) {
    py::object depth_obj = feature_dict[py_str("depth")];
    if (py::isinstance<py::str>(depth_obj)) {
      const std::string depth_str = to_lower(py::str(depth_obj));
      if (depth_str == "through") {
        return sheet_thickness;
      }
      try {
        return std::stod(depth_str);
      } catch (...) {
        return 0.0;
      }
    }
    return as_double(depth_obj, 0.0);
  }
  return 0.0;
}

ShapeInput parse_shape(const py::dict &shape_dict, double sheet_thickness) {
  ShapeInput out;
  if (dict_contains(shape_dict, "id")) {
    out.id = py::str(shape_dict[py_str("id")]);
  }
  out.shape_kind = parse_shape_kind(shape_dict);

  if (dict_contains(shape_dict, "geometry")) {
    const py::dict geom = shape_dict[py_str("geometry")].cast<py::dict>();
    out.width = as_double(dict_get(geom, "w_mm"), 0.0);
    out.height = as_double(dict_get(geom, "h_mm"), 0.0);
    out.diameter = as_double(dict_get(geom, "diameter_mm"), 0.0);
  }

  std::tie(out.center_x, out.center_y) = parse_center_xy(shape_dict);

  py::dict feature = dict_contains(shape_dict, "feature") ? shape_dict[py_str("feature")].cast<py::dict>() : py::dict();
  out.feature_kind = parse_feature_kind(feature);
  out.depth = feature_depth_mm(feature, sheet_thickness);

  bool explicit_through = false;
  if (dict_contains(feature, "depth")) {
    py::object depth_obj = feature[py_str("depth")];
    if (py::isinstance<py::str>(depth_obj)) {
      explicit_through = to_lower(py::str(depth_obj)) == "through";
    }
  }
  out.through = explicit_through || (out.depth >= sheet_thickness - 1e-6);

  return out;
}

std::vector<ShapeInput> parse_shapes(const py::list &shapes, double sheet_thickness) {
  std::vector<ShapeInput> out;
  out.reserve(shapes.size());
  for (const auto &item : shapes) {
    py::dict shape_dict = py::reinterpret_borrow<py::dict>(item);
    out.push_back(parse_shape(shape_dict, sheet_thickness));
  }
  return out;
}

TopoDS_Shape make_box(double center_x, double center_y, double z_low, double width, double height, double depth) {
  gp_Pnt corner(center_x - 0.5 * width, center_y - 0.5 * height, z_low);
  return BRepPrimAPI_MakeBox(corner, width, height, depth).Solid();
}

TopoDS_Shape make_cylinder(double center_x, double center_y, double z_low, double radius, double height) {
  gp_Ax2 axis(gp_Pnt(center_x, center_y, z_low), gp_Dir(0.0, 0.0, 1.0));
  return BRepPrimAPI_MakeCylinder(axis, radius, height).Solid();
}

void ensure_cut_done(const BRepAlgoAPI_Cut &op, const std::string &context) {
  if (!op.IsDone()) {
    throw std::runtime_error("Boolean cut failed: " + context);
  }
}

TopoDS_Shape fix_shape(const TopoDS_Shape &shape) {
  ShapeFix_Shape fixer(shape);
  fixer.Perform();
  return fixer.Shape();
}

struct GeometryResult {
  TopoDS_Shape sheet;
  std::vector<std::pair<std::string, TopoDS_Shape>> parts;
};

GeometryResult build_geometry(const SheetSpec &sheet,
                              const std::vector<ShapeInput> &shapes,
                              double kerf_mm,
                              bool include_floating_parts) {
  const double kerf = std::max(0.0, kerf_mm);
  const double extra = std::max(1.0, 0.1 * sheet.thickness);

  GeometryResult result;
  result.sheet = make_box(0.0, 0.0, -sheet.thickness, sheet.width, sheet.height, sheet.thickness);
  result.sheet = fix_shape(result.sheet);

  // Collect pocket cutters to apply to both sheet and parts after we know all parts.
  std::vector<TopoDS_Shape> pocket_cutters;

  for (const auto &shape : shapes) {
    if (shape.shape_kind != ShapeKind::Rect && shape.shape_kind != ShapeKind::Circle) {
      continue;  // unsupported geometry
    }

    if (shape.feature_kind == FeatureKind::Profile && shape.through) {
      if (shape.shape_kind == ShapeKind::Rect) {
        const double cut_w = shape.width + kerf;
        const double cut_h = shape.height + kerf;
        TopoDS_Shape cutter = make_box(shape.center_x, shape.center_y,
                                       -sheet.thickness - extra,
                                       std::max(0.0, cut_w),
                                       std::max(0.0, cut_h),
                                       sheet.thickness + 2.0 * extra);
        BRepAlgoAPI_Cut cut(result.sheet, cutter);
        ensure_cut_done(cut, "rectangular through profile");
        result.sheet = fix_shape(cut.Shape());

        if (include_floating_parts && shape.width > 0.0 && shape.height > 0.0) {
          TopoDS_Shape slug = make_box(shape.center_x, shape.center_y,
                                       -sheet.thickness,
                                       std::max(0.0, shape.width),
                                       std::max(0.0, shape.height),
                                       sheet.thickness);
          result.parts.emplace_back(shape.id, fix_shape(slug));
        }
      } else if (shape.shape_kind == ShapeKind::Circle) {
        const double radius = 0.5 * shape.diameter;
        const double cut_radius = radius + 0.5 * kerf;
        TopoDS_Shape cutter = make_cylinder(shape.center_x, shape.center_y,
                                            -sheet.thickness - extra,
                                            std::max(0.0, cut_radius),
                                            sheet.thickness + 2.0 * extra);
        BRepAlgoAPI_Cut cut(result.sheet, cutter);
        ensure_cut_done(cut, "cylindrical through profile");
        result.sheet = fix_shape(cut.Shape());

        if (include_floating_parts && radius > 0.0) {
          TopoDS_Shape slug = make_cylinder(shape.center_x, shape.center_y,
                                            -sheet.thickness,
                                            std::max(0.0, radius),
                                            sheet.thickness);
          result.parts.emplace_back(shape.id, fix_shape(slug));
        }
      }
      continue;
    }

    const bool pocket_like_profile =
        (shape.feature_kind == FeatureKind::Profile && !shape.through && shape.depth > 0.0);

    if (((shape.feature_kind == FeatureKind::Pocket || shape.feature_kind == FeatureKind::Engrave) && shape.depth > 0.0) ||
        pocket_like_profile) {
      const double depth = std::clamp(shape.depth, 0.0, sheet.thickness);
      if (depth <= 0.0) {
        continue;
      }
      if (shape.shape_kind == ShapeKind::Rect) {
        TopoDS_Shape cutter = make_box(shape.center_x, shape.center_y,
                                       -depth,
                                       std::max(0.0, shape.width),
                                       std::max(0.0, shape.height),
                                       depth + 1e-6);
        pocket_cutters.push_back(cutter);
      } else if (shape.shape_kind == ShapeKind::Circle) {
        const double radius = 0.5 * shape.diameter;
        TopoDS_Shape cutter = make_cylinder(shape.center_x, shape.center_y,
                                            -depth,
                                            std::max(0.0, radius),
                                            depth + 1e-6);
        pocket_cutters.push_back(cutter);
      }
    }
  }

  // Apply all pocket cutters to the sheet and any floating parts.
  for (const auto &cutter : pocket_cutters) {
    BRepAlgoAPI_Cut cut_sheet(result.sheet, cutter);
    ensure_cut_done(cut_sheet, "apply pocket to sheet");
    result.sheet = fix_shape(cut_sheet.Shape());

    for (auto &entry : result.parts) {
      BRepAlgoAPI_Cut cut_part(entry.second, cutter);
      ensure_cut_done(cut_part, "apply pocket to part");
      entry.second = fix_shape(cut_part.Shape());
    }
  }

  return result;
}

std::vector<std::pair<std::string, ShapeInput>> filter_parts(const std::vector<ShapeInput> &shapes) {
  std::vector<std::pair<std::string, ShapeInput>> out;
  for (const auto &shape : shapes) {
    if (shape.feature_kind == FeatureKind::Profile && shape.through &&
        (shape.shape_kind == ShapeKind::Rect || shape.shape_kind == ShapeKind::Circle)) {
      out.emplace_back(shape.id, shape);
    }
  }
  return out;
}

py::dict make_solid_dict(const std::string &kind,
                         const std::string &shape,
                         const std::string &id,
                         double width,
                         double height,
                         double thickness,
                         double center_x,
                         double center_y) {
  py::dict d;
  d["kind"] = kind;
  d["shape"] = shape;
  d["id"] = id.empty() ? py::none() : py::cast(id);
  d["width_mm"] = width;
  d["height_mm"] = height;
  d["thickness_mm"] = thickness;
  d["center_xy_mm"] = py::make_tuple(center_x, center_y);
  return d;
}

py::dict make_pocket_dict(const ShapeInput &shape) {
  py::dict d;
  d["shape"] = (shape.shape_kind == ShapeKind::Circle) ? "circle" : "rect";
  d["id"] = shape.id.empty() ? py::none() : py::cast(shape.id);
  d["depth_mm"] = shape.depth;
  d["center_xy_mm"] = py::make_tuple(shape.center_x, shape.center_y);
  d["width_mm"] = shape.width;
  d["height_mm"] = shape.height;
  d["diameter_mm"] = shape.diameter;
  return d;
}

void write_step(const TopoDS_Shape &sheet,
                const std::vector<std::pair<std::string, TopoDS_Shape>> &parts,
                const std::string &path) {
  STEPControl_Writer writer;
  IFSelect_ReturnStatus status = writer.Transfer(sheet, STEPControl_AsIs);
  if (status != IFSelect_RetDone) {
    throw std::runtime_error("Failed to transfer sheet to STEP controller");
  }
  for (const auto &entry : parts) {
    status = writer.Transfer(entry.second, STEPControl_AsIs);
    if (status != IFSelect_RetDone) {
      throw std::runtime_error("Failed to transfer part to STEP controller");
    }
  }
  status = writer.Write(path.c_str());
  if (status != IFSelect_RetDone) {
    throw std::runtime_error("Failed to write STEP file: " + path);
  }
}

void write_stl(const TopoDS_Shape &shape,
               const std::string &path,
               double deflection) {
  const double mesh_deflection = std::max(0.01, deflection);
  BRepMesh_IncrementalMesh mesher(shape, mesh_deflection);
  mesher.Perform();

  StlAPI_Writer writer;
  writer.ASCIIMode() = Standard_True;
  if (!writer.Write(shape, path.c_str())) {
    throw std::runtime_error("Failed to write STL file: " + path);
  }
}

}  // namespace

py::dict build_model_binding(const py::dict &sheet_dict,
                             const py::list &shape_list,
                             double kerf_mm,
                             bool include_parts) {
  SheetSpec sheet;
  sheet.width = sheet_dict[py_str("width_mm")].cast<double>();
  sheet.height = sheet_dict[py_str("height_mm")].cast<double>();
  sheet.thickness = sheet_dict[py_str("thickness_mm")].cast<double>();

  const auto shapes = parse_shapes(shape_list, sheet.thickness);

  py::dict model;
  model["sheet"] = make_solid_dict("sheet", "rect", "",
                                    sheet.width, sheet.height, sheet.thickness,
                                    0.0, 0.0);

  py::list parts_out;
  if (include_parts) {
    for (const auto &entry : filter_parts(shapes)) {
      const auto &shape = entry.second;
      if (shape.shape_kind == ShapeKind::Rect) {
        parts_out.append(make_solid_dict("part", "rect", entry.first,
                                         shape.width, shape.height, sheet.thickness,
                                         shape.center_x, shape.center_y));
      } else if (shape.shape_kind == ShapeKind::Circle) {
        parts_out.append(make_solid_dict("part", "circle", entry.first,
                                         shape.diameter, shape.diameter, sheet.thickness,
                                         shape.center_x, shape.center_y));
      }
    }
  }
  model["parts"] = std::move(parts_out);

  py::list pockets;
  for (const auto &shape : shapes) {
    const bool pocket_like_profile =
        (shape.feature_kind == FeatureKind::Profile && !shape.through && shape.depth > 0.0);

    if (((shape.feature_kind == FeatureKind::Pocket || shape.feature_kind == FeatureKind::Engrave) && shape.depth > 0.0) ||
        pocket_like_profile) {
      pockets.append(make_pocket_dict(shape));
    }
  }
  model["pockets"] = std::move(pockets);
  model["kerf_mm"] = kerf_mm;
  return model;
}

py::list export_stl_binding(const py::dict &sheet_dict,
                            const py::list &shape_list,
                            const std::string &output_path,
                            double kerf_mm,
                            bool include_sheet,
                            bool include_parts,
                            double mesh_tolerance) {
  SheetSpec sheet;
  sheet.width = as_double(dict_get(sheet_dict, "width_mm"), 0.0);
  sheet.height = as_double(dict_get(sheet_dict, "height_mm"), 0.0);
  sheet.thickness = as_double(dict_get(sheet_dict, "thickness_mm"), 0.0);

  auto shapes = parse_shapes(shape_list, sheet.thickness);
  GeometryResult geometry = build_geometry(sheet, shapes, kerf_mm, include_parts);

  py::list outputs;
  if (include_sheet) {
    TopoDS_Shape sheet_shape = geometry.sheet;
    if (include_parts && !geometry.parts.empty()) {
      BRep_Builder builder;
      TopoDS_Compound compound;
      builder.MakeCompound(compound);
      builder.Add(compound, geometry.sheet);
      for (const auto &entry : geometry.parts) {
        builder.Add(compound, entry.second);
      }
      sheet_shape = compound;
    }

    write_stl(sheet_shape, output_path, mesh_tolerance);
    outputs.append(output_path);
  }

  if (include_parts) {
    std::size_t index = 1;
    for (const auto &entry : geometry.parts) {
      const std::string part_path = output_path.substr(0, output_path.find_last_of('.')) +
                                    "_part" + std::to_string(index) + ".stl";
      write_stl(entry.second, part_path, mesh_tolerance);
      outputs.append(part_path);
      ++index;
    }
  }

  return outputs;
}

void export_step_binding(const py::dict &sheet_dict,
                         const py::list &shape_list,
                         const std::string &output_path,
                         double kerf_mm,
                         bool include_parts) {
  SheetSpec sheet;
  sheet.width = as_double(dict_get(sheet_dict, "width_mm"), 0.0);
  sheet.height = as_double(dict_get(sheet_dict, "height_mm"), 0.0);
  sheet.thickness = as_double(dict_get(sheet_dict, "thickness_mm"), 0.0);

  auto shapes = parse_shapes(shape_list, sheet.thickness);
  GeometryResult geometry = build_geometry(sheet, shapes, kerf_mm, include_parts);
  write_step(geometry.sheet, geometry.parts, output_path);
}

PYBIND11_MODULE(_cad_native, m) {
  m.doc() = "Native CAD helper bindings";

  m.def("build_model", &build_model_binding,
        py::arg("sheet"),
        py::arg("shapes"),
        py::arg("kerf_mm") = 0.0,
        py::arg("include_parts") = true,
        "Produce a lightweight summary of the sheet, floating parts, and pockets.");

  m.def("export_stl", &export_stl_binding,
        py::arg("sheet"),
        py::arg("shapes"),
        py::arg("output_path"),
        py::arg("kerf_mm") = 0.0,
        py::arg("include_sheet") = false,
        py::arg("include_floating_parts") = true,
        py::arg("mesh_tolerance") = 0.3,
        "Write ASCII STL files for the sheet and optional floating parts.");

  m.def("export_step", &export_step_binding,
        py::arg("sheet"),
        py::arg("shapes"),
        py::arg("output_path"),
        py::arg("kerf_mm") = 0.0,
        py::arg("include_floating_parts") = true,
        "Write a STEP file containing the sheet and optional floating parts.");
}
