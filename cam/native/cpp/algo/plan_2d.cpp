#include "millui/native/algo/plan_2d.hpp"

#include <cmath>
#include <limits>
#include <optional>
#include <sstream>

namespace millui::native::algo {

namespace {

constexpr double kEps = 1e-9;

std::string fmt3(double v) {
  std::ostringstream oss;
  oss.setf(std::ios::fixed, std::ios::floatfield);
  oss.precision(3);
  oss << v;
  return oss.str();
}

PathMove make_comment(std::string text) {
  PathMove mv;
  mv.kind = "comment";
  mv.text = std::move(text);
  return mv;
}

PathMove make_set_rpm(double rpm) {
  PathMove mv;
  mv.kind = "set_rpm";
  mv.rpm = rpm;
  return mv;
}

PathMove make_set_feed(double feed) {
  PathMove mv;
  mv.kind = "set_feed";
  mv.feed = feed;
  return mv;
}

PathMove make_rapid(double x, double y, double z) {
  PathMove mv;
  mv.kind = "rapid";
  mv.x = x;
  mv.y = y;
  mv.z = z;
  return mv;
}

PathMove make_cut(std::optional<double> x, std::optional<double> y, std::optional<double> z,
                  std::optional<double> feed = std::nullopt) {
  PathMove mv;
  mv.kind = "cut";
  mv.x = x.value_or(std::numeric_limits<double>::quiet_NaN());
  mv.y = y.value_or(std::numeric_limits<double>::quiet_NaN());
  mv.z = z.value_or(std::numeric_limits<double>::quiet_NaN());
  mv.feed = feed.value_or(std::numeric_limits<double>::quiet_NaN());
  return mv;
}

PathMove make_retract(double z) {
  PathMove mv;
  mv.kind = "retract";
  mv.z = z;
  return mv;
}

struct Bounds {
  double minx = 0.0;
  double miny = 0.0;
  double maxx = 0.0;
  double maxy = 0.0;
};

Bounds bounds_of(const Polygon& poly) {
  Bounds b;
  if (poly.empty()) {
    return b;
  }
  b.minx = b.maxx = poly.front().x;
  b.miny = b.maxy = poly.front().y;
  for (const auto& p : poly) {
    b.minx = std::min(b.minx, p.x);
    b.miny = std::min(b.miny, p.y);
    b.maxx = std::max(b.maxx, p.x);
    b.maxy = std::max(b.maxy, p.y);
  }
  return b;
}

}  // namespace

Paths plan_pocket(const PlanarFace& face, const Tool& tool, double step_over_mm, double step_down_mm,
                  double safe_z_mm) {
  const Bounds b = bounds_of(face.outer);
  const double safe_z = safe_z_mm;
  const double depth = -std::abs(face.depth);
  const double tool_d = tool.diameter <= 0.0 ? 3.0 : tool.diameter;
  const double default_step_down = std::min(3.0, 0.5 * tool_d);
  const double step_down = step_down_mm > kEps ? step_down_mm : default_step_down;
  const double step_over = std::max(0.1, step_over_mm);

  Paths paths(1);
  Path& moves = paths.front();
  moves.reserve(64);

  moves.push_back(make_comment(
      "pocket_raster so=" + fmt3(step_over) + " sd=" + fmt3(step_down) +
      " depth=" + fmt3(std::abs(depth))));
  moves.push_back(make_set_rpm(tool.rpm));
  moves.push_back(make_set_feed(tool.feed_xy));

  std::vector<double> z_levels;
  double z = 0.0;
  while (z > depth + kEps) {
    double z_next = std::max(depth, z - step_down);
    z_levels.push_back(z_next);
    z = z_next;
    if (std::abs(z - depth) < kEps) {
      break;
    }
  }

  int direction = 1;
  for (double layer_z : z_levels) {
    double y = b.miny;
    while (y <= b.maxy + kEps) {
      double x_start = direction == 1 ? b.minx : b.maxx;
      double x_end = direction == 1 ? b.maxx : b.minx;
      moves.push_back(make_rapid(x_start, y, safe_z));
      moves.push_back(make_cut(std::nullopt, std::nullopt, layer_z, tool.feed_z));
      moves.push_back(make_set_feed(tool.feed_xy));
      moves.push_back(make_cut(x_end, y, std::nullopt));
      moves.push_back(make_retract(safe_z));
      y += step_over;
      direction *= -1;
    }
  }

  return paths;
}

Paths plan_profile(const Polygon& boundary, const Tool& tool, double total_depth_mm, double step_down_mm,
                   double safe_z) {
  const double depth_target = -std::abs(total_depth_mm);

  Paths paths(1);
  Path& moves = paths.front();
  moves.reserve(boundary.size() * 4);
  moves.push_back(make_comment("profile_outline"));
  moves.push_back(make_set_rpm(tool.rpm));
  moves.push_back(make_set_feed(tool.feed_xy));

  const double step_down = step_down_mm <= 0.0 ? 2.0 : step_down_mm;
  double z = 0.0;
  while (z > depth_target) {
    z = std::max(z - step_down, depth_target);
    if (boundary.empty()) {
      break;
    }
    const Vec2& start = boundary.front();
    moves.push_back(make_rapid(start.x, start.y, safe_z));
    moves.push_back(make_cut(std::nullopt, std::nullopt, z, tool.feed_z));
    moves.push_back(make_set_feed(tool.feed_xy));
    for (std::size_t i = 1; i < boundary.size(); ++i) {
      const Vec2& p = boundary[i];
      moves.push_back(make_cut(p.x, p.y, std::nullopt));
    }
    moves.push_back(make_retract(safe_z));
  }

  return paths;
}

Paths plan_drill(const std::vector<Hole>& holes, const Tool& tool, double peck_mm, double safe_z) {
  Paths paths(1);
  Path& moves = paths.front();
  moves.reserve(holes.size() * 8);

  moves.push_back(make_comment("drill_peck"));
  moves.push_back(make_set_rpm(tool.rpm));
  moves.push_back(make_set_feed(tool.feed_z));

  const double peck = peck_mm <= 0.0 ? 3.0 : peck_mm;
  for (const auto& hole : holes) {
    moves.push_back(make_rapid(hole.x, hole.y, safe_z));
    double z = 0.0;
    const double depth = -std::abs(hole.depth);
    while (z > depth + kEps) {
      double z_next = std::max(depth, z - peck);
      moves.push_back(make_cut(std::nullopt, std::nullopt, z_next));
      moves.push_back(make_retract(safe_z));
      z = z_next;
      if (std::abs(z - depth) < kEps) {
        break;
      }
    }
  }

  return paths;
}

Paths plan_bore_helical(const Hole& hole, const Tool& tool, double step_down_mm, double safe_z) {
  Paths paths(1);
  Path& moves = paths.front();

  const double tool_d = tool.diameter <= 0.0 ? 1.0 : tool.diameter;
  const double D = hole.diameter;
  if (D <= tool_d) {
    return paths;
  }

  const double target = -std::abs(hole.depth);
  const double r_eff = std::max(0.01, (D - tool_d) * 0.5);
  const double step_down = step_down_mm <= 0.0 ? 2.5 : step_down_mm;
  const int segments = 60;

  moves.push_back(make_comment("bore_helical D=" + fmt3(D) + " tool=" + fmt3(tool_d) + " r_eff=" + fmt3(r_eff)));
  moves.push_back(make_set_rpm(tool.rpm));
  moves.push_back(make_set_feed(tool.feed_xy));
  moves.push_back(make_rapid(hole.x + r_eff, hole.y, safe_z));

  auto circle_point = [&](int i, double radius) {
    const double t = 2.0 * M_PI * (static_cast<double>(i) / segments);
    return Vec2{hole.x + radius * std::cos(t), hole.y + radius * std::sin(t)};
  };

  double z = 0.0;
  while (z > target + kEps) {
    double z_next = std::max(target, z - step_down);
    for (int i = 1; i <= segments; ++i) {
      double t = static_cast<double>(i) / segments;
      double z_i = z + (z_next - z) * t;
      Vec2 pt = circle_point(i, r_eff);
      if (i == 1) {
        moves.push_back(make_cut(std::nullopt, std::nullopt, z_i, tool.feed_z));
        moves.push_back(make_set_feed(tool.feed_xy));
      }
      moves.push_back(make_cut(pt.x, pt.y, z_i));
    }
    z = z_next;

    for (int i = 0; i <= segments; ++i) {
      Vec2 pt = circle_point(i, r_eff);
      if (i == 0) {
        moves.push_back(make_cut(pt.x, pt.y, std::nullopt));
      } else {
        moves.push_back(make_cut(pt.x, pt.y, std::nullopt));
      }
    }
  }

  moves.push_back(make_retract(safe_z));
  return paths;
}

}  // namespace millui::native::algo
