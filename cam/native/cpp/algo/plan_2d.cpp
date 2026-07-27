#include "millui/native/algo/plan_2d.hpp"

#include <algorithm>
#include <cmath>
#include <numbers>
#include <optional>
#include <span>
#include <sstream>
#include <vector>

namespace millui::native::algo {

namespace {

constexpr double kEps = 1e-9;
constexpr double kDefaultToolDiameterMm = 3.0;
constexpr double kDefaultStepDownCapMm = 3.0;
constexpr double kMinStepOverMm = 0.1;
constexpr double kDefaultPeckMm = 3.0;
constexpr double kDefaultRetractClearanceMm = 2.0;
constexpr double kProfileDefaultStepDownMm = 2.0;
constexpr double kBoreDefaultToolDiameterMm = 1.0;
constexpr double kBoreDefaultStepDownMm = 2.5;
constexpr int kHelixSegments = 60;

std::vector<double> build_z_levels(double depth, double step_down) {
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
  return z_levels;
}

std::string fmt3(double v) {
  std::ostringstream oss;
  oss.setf(std::ios::fixed, std::ios::floatfield);
  oss.precision(3);
  oss << v;
  return oss.str();
}

Move make_comment(std::string text) {
  return Comment{std::move(text)};
}

Move make_set_rpm(double rpm) {
  return SetRpm{rpm};
}

Move make_set_feed(double feed) {
  return SetFeed{feed};
}

Move make_rapid(double x, double y, double z) {
  return Rapid{x, y, z};  // planners always pass concrete axes; optionals fill from doubles
}

Move make_cut(std::optional<double> x, std::optional<double> y, std::optional<double> z,
              std::optional<double> feed = std::nullopt) {
  return Cut{x, y, z, feed};
}

Move make_retract(double z) {
  return Retract{z};
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

double seg_length(const Vec2& a, const Vec2& b) {
  return std::hypot(b.x - a.x, b.y - a.y);
}

void emit_ramp_or_plunge(Path& moves, std::span<const Vec2> path,
                         double prev_z, double target_z,
                         double ramp_angle_deg, double safe_z,
                         double feed_xy, double feed_z,
                         bool keepdown = false) {
  if (path.empty()) return;

  double step_down = std::abs(target_z - prev_z);
  double ramp_dist = 0.0;
  if (ramp_angle_deg > kEps && step_down > kEps) {
    ramp_dist = step_down / std::tan(ramp_angle_deg * std::numbers::pi / 180.0);
  }

  const Vec2& end_point = path.back();

  if (ramp_dist < kEps || path.size() < 2) {
    moves.push_back(make_rapid(end_point.x, end_point.y, safe_z));
    moves.push_back(make_cut(std::nullopt, std::nullopt, target_z, feed_z));
    return;
  }

  double avail = 0.0;
  for (size_t i = 0; i + 1 < path.size(); ++i) {
    avail += seg_length(path[i], path[i + 1]);
  }

  if (avail < ramp_dist - kEps) {
    moves.push_back(make_rapid(end_point.x, end_point.y, safe_z));
    moves.push_back(make_comment("ramp fallback: path too short"));
    moves.push_back(make_cut(std::nullopt, std::nullopt, target_z, feed_z));
    return;
  }

  const Vec2& ramp_start = path[0];
  if (!keepdown) {
    moves.push_back(make_rapid(ramp_start.x, ramp_start.y, safe_z));
    if (std::abs(prev_z) > kEps) {
      moves.push_back(make_cut(ramp_start.x, ramp_start.y, prev_z, feed_z));
    }
  }

  double remaining = ramp_dist;
  double z = prev_z;
  for (size_t i = 0; i + 1 < path.size() && remaining > kEps; ++i) {
    double sl = seg_length(path[i], path[i + 1]);
    if (sl < kEps) continue;
    double use = std::min(sl, remaining);
    double frac = use / sl;
    double nx = path[i].x + (path[i + 1].x - path[i].x) * frac;
    double ny = path[i].y + (path[i + 1].y - path[i].y) * frac;
    double dz = step_down * (use / ramp_dist);
    z -= dz;
    moves.push_back(make_cut(nx, ny, z, feed_xy));
    remaining -= use;
  }

  moves.push_back(make_cut(end_point.x, end_point.y, target_z, feed_xy));
}

double shoelace_area(const Polygon& poly) {
  double area = 0.0;
  size_t n = poly.size();
  for (size_t i = 0; i < n; ++i) {
    size_t j = (i + 1) % n;
    area += poly[i].x * poly[j].y;
    area -= poly[j].x * poly[i].y;
  }
  return 0.5 * area;
}

bool is_convex(const Polygon& poly) {
  size_t n = poly.size();
  if (n < 3) return false;

  bool has_pos = false;
  bool has_neg = false;
  for (size_t i = 0; i < n; ++i) {
    size_t j = (i + 1) % n;
    size_t k = (i + 2) % n;
    double dx1 = poly[j].x - poly[i].x;
    double dy1 = poly[j].y - poly[i].y;
    double dx2 = poly[k].x - poly[j].x;
    double dy2 = poly[k].y - poly[j].y;
    double cross = dx1 * dy2 - dy1 * dx2;
    if (cross > kEps) has_pos = true;
    if (cross < -kEps) has_neg = true;
    if (has_pos && has_neg) return false;
  }
  return true;
}

Polygon ensure_cw(const Polygon& poly) {
  if (shoelace_area(poly) > 0.0) {
    Polygon rev(poly.rbegin(), poly.rend());
    return rev;
  }
  return poly;
}

Polygon strip_closing_vertex(const Polygon& poly) {
  if (poly.size() >= 2 &&
      std::abs(poly.front().x - poly.back().x) < kEps &&
      std::abs(poly.front().y - poly.back().y) < kEps) {
    return Polygon(poly.begin(), poly.end() - 1);
  }
  return poly;
}

Polygon inset_convex(const Polygon& poly, double offset) {
  size_t n = poly.size();
  if (n < 3 || offset < kEps) return poly;

  double area = shoelace_area(poly);
  double winding = (area > 0.0) ? -1.0 : 1.0;

  struct ShiftedEdge {
    Vec2 p0, p1;
  };
  std::vector<ShiftedEdge> edges(n);

  for (size_t i = 0; i < n; ++i) {
    size_t j = (i + 1) % n;
    double dx = poly[j].x - poly[i].x;
    double dy = poly[j].y - poly[i].y;
    double len = std::hypot(dx, dy);
    if (len < kEps) {
      edges[i] = {{poly[i].x, poly[i].y}, {poly[j].x, poly[j].y}};
      continue;
    }
    double nx = winding * dy / len;
    double ny = winding * (-dx) / len;
    double sx = offset * nx;
    double sy = offset * ny;
    edges[i] = {
        {poly[i].x + sx, poly[i].y + sy},
        {poly[j].x + sx, poly[j].y + sy}};
  }

  Polygon result(n);
  for (size_t i = 0; i < n; ++i) {
    size_t prev = (i + n - 1) % n;
    const auto& e0 = edges[prev];
    const auto& e1 = edges[i];

    double d0x = e0.p1.x - e0.p0.x;
    double d0y = e0.p1.y - e0.p0.y;
    double d1x = e1.p1.x - e1.p0.x;
    double d1y = e1.p1.y - e1.p0.y;

    double denom = d0x * d1y - d0y * d1x;
    if (std::abs(denom) < kEps) {
      result[i] = e1.p0;
      continue;
    }

    double dx = e1.p0.x - e0.p0.x;
    double dy = e1.p0.y - e0.p0.y;
    double t = (dx * d1y - dy * d1x) / denom;
    result[i] = {e0.p0.x + t * d0x, e0.p0.y + t * d0y};
  }

  double result_area = shoelace_area(result);
  if ((area > 0.0 && result_area <= kEps) || (area < 0.0 && result_area >= -kEps)) {
    return {};
  }
  if (std::abs(result_area) >= std::abs(area) - kEps) {
    return {};
  }
  if (!is_convex(result)) {
    return {};
  }
  return result;
}

class ConvexPolygon {
 public:
  static std::optional<ConvexPolygon> try_from(const Polygon& poly) {
    Polygon p = ensure_cw(strip_closing_vertex(poly));
    if (!is_convex(p)) {
      return std::nullopt;
    }
    return ConvexPolygon(std::move(p));
  }

  const Polygon& points() const { return points_; }

 private:
  explicit ConvexPolygon(Polygon points) : points_(std::move(points)) {}
  Polygon points_;
};

Polygon inset(const ConvexPolygon& poly, double offset) {
  return inset_convex(poly.points(), offset);
}

size_t longest_edge_index(const Polygon& poly) {
  size_t n = poly.size();
  size_t best = 0;
  double best_len = 0.0;
  for (size_t i = 0; i < n; ++i) {
    size_t j = (i + 1) % n;
    double len = seg_length(poly[i], poly[j]);
    if (len > best_len) {
      best_len = len;
      best = i;
    }
  }
  return best;
}

std::vector<double> scanline_intersections(const Polygon& poly, double y) {
  std::vector<double> xs;
  size_t n = poly.size();
  for (size_t i = 0; i < n; ++i) {
    size_t j = (i + 1) % n;
    const Vec2& a = poly[i];
    const Vec2& b = poly[j];

    if (std::abs(a.y - b.y) < kEps) continue;

    double y_min = std::min(a.y, b.y);
    double y_max = std::max(a.y, b.y);

    if (y < y_min - kEps || y > y_max + kEps) continue;
    if (std::abs(y - y_max) < kEps) continue;

    double t = (y - a.y) / (b.y - a.y);
    t = std::clamp(t, 0.0, 1.0);
    xs.push_back(a.x + t * (b.x - a.x));
  }
  std::sort(xs.begin(), xs.end());
  return xs;
}

Paths plan_pocket_raster_clipped(const Polygon& outer_stripped, const Tool& tool, double depth_val,
                                  double step_over_mm, double step_down_mm,
                                  double safe_z_mm, double ramp_angle_deg) {
  Polygon poly = ensure_cw(outer_stripped);
  const Bounds b = bounds_of(poly);
  const double safe_z = safe_z_mm;
  const double depth = -std::abs(depth_val);
  const double tool_d = tool.diameter <= 0.0 ? kDefaultToolDiameterMm : tool.diameter;
  const double tool_r = 0.5 * tool_d;
  const double default_step_down = std::min(kDefaultStepDownCapMm, 0.5 * tool_d);
  const double step_down = step_down_mm > kEps ? step_down_mm : default_step_down;
  const double step_over = std::max(kMinStepOverMm, step_over_mm);

  Paths paths(1);
  Path& moves = paths.front();
  moves.reserve(128);

  moves.push_back(make_comment(
      "pocket_raster_clipped so=" + fmt3(step_over) + " sd=" + fmt3(step_down) +
      " depth=" + fmt3(std::abs(depth))));
  moves.push_back(make_set_rpm(tool.rpm));
  moves.push_back(make_set_feed(tool.feed_xy));

  const std::vector<double> z_levels = build_z_levels(depth, step_down);

  int direction = 1;
  double prev_z = 0.0;
  for (double layer_z : z_levels) {
    double y = b.miny + tool_r;
    double y_max = b.maxy - tool_r;
    while (y <= y_max + kEps) {
      auto xs = scanline_intersections(poly, y);

      for (size_t k = 0; k + 1 < xs.size(); k += 2) {
        double x_left = xs[k] + tool_r;
        double x_right = xs[k + 1] - tool_r;
        if (x_right < x_left + kEps) continue;

        double x_start = direction == 1 ? x_left : x_right;
        double x_end = direction == 1 ? x_right : x_left;

        if (std::abs(prev_z - layer_z) < kEps) {
          moves.push_back(make_rapid(x_start, y, safe_z));
          moves.push_back(make_cut(std::nullopt, std::nullopt, layer_z, tool.feed_z));
        } else {
          Vec2 ramp_path[2] = {{x_start, y}, {x_end, y}};
          emit_ramp_or_plunge(moves, ramp_path, prev_z, layer_z,
                              ramp_angle_deg, safe_z, tool.feed_xy, tool.feed_z);
        }
        moves.push_back(make_set_feed(tool.feed_xy));
        moves.push_back(make_cut(x_end, y, std::nullopt));
        moves.push_back(make_retract(safe_z));
        prev_z = layer_z;
      }

      y += step_over;
      direction *= -1;
    }
  }

  size_t n = poly.size();
  if (n >= 3) {
    Polygon inset = inset_convex(poly, tool_r);
    const Polygon& profile_poly = inset.empty() ? poly : inset;
    size_t pn = profile_poly.size();

    moves.push_back(make_comment("finish_perimeter_clipped"));

    for (double layer_z : z_levels) {
      const Vec2& start = profile_poly[0];
      moves.push_back(make_rapid(start.x, start.y, safe_z));
      moves.push_back(make_cut(std::nullopt, std::nullopt, layer_z, tool.feed_z));
      moves.push_back(make_set_feed(tool.feed_xy));
      for (size_t i = 1; i < pn; ++i) {
        moves.push_back(make_cut(profile_poly[i].x, profile_poly[i].y, std::nullopt));
      }
      moves.push_back(make_cut(profile_poly[0].x, profile_poly[0].y, std::nullopt));
      moves.push_back(make_retract(safe_z));
    }
  }

  return paths;
}

Paths plan_pocket_raster(const PlanarFace& face, const Tool& tool, double step_over_mm, double step_down_mm,
                         double safe_z_mm, double ramp_angle_deg) {
  const Bounds b = bounds_of(face.outer);
  const double safe_z = safe_z_mm;
  const double depth = -std::abs(face.depth);
  const double tool_d = tool.diameter <= 0.0 ? kDefaultToolDiameterMm : tool.diameter;
  const double default_step_down = std::min(kDefaultStepDownCapMm, 0.5 * tool_d);
  const double step_down = step_down_mm > kEps ? step_down_mm : default_step_down;
  const double step_over = std::max(kMinStepOverMm, step_over_mm);

  Paths paths(1);
  Path& moves = paths.front();
  moves.reserve(64);

  moves.push_back(make_comment(
      "pocket_raster so=" + fmt3(step_over) + " sd=" + fmt3(step_down) +
      " depth=" + fmt3(std::abs(depth))));
  moves.push_back(make_set_rpm(tool.rpm));
  moves.push_back(make_set_feed(tool.feed_xy));

  const std::vector<double> z_levels = build_z_levels(depth, step_down);

  int direction = 1;
  double prev_z = 0.0;
  for (double layer_z : z_levels) {
    double y = b.miny;
    while (y <= b.maxy + kEps) {
      double x_start = direction == 1 ? b.minx : b.maxx;
      double x_end = direction == 1 ? b.maxx : b.minx;
      Vec2 ramp_path[2] = {{x_start, y}, {x_end, y}};
      emit_ramp_or_plunge(moves, ramp_path, prev_z, layer_z, ramp_angle_deg, safe_z, tool.feed_xy, tool.feed_z);
      moves.push_back(make_set_feed(tool.feed_xy));
      moves.push_back(make_cut(x_end, y, std::nullopt));
      moves.push_back(make_retract(safe_z));
      prev_z = layer_z;
      y += step_over;
      direction *= -1;
    }
  }

  return paths;
}

Paths plan_pocket_spiral(const Polygon& outer_stripped, const Tool& tool, double depth_val,
                         double step_over_mm, double step_down_mm,
                         double safe_z_mm, double ramp_angle_deg) {
  const double safe_z = safe_z_mm;
  const double depth = -std::abs(depth_val);
  const double tool_d = tool.diameter <= 0.0 ? kDefaultToolDiameterMm : tool.diameter;
  const double tool_r = 0.5 * tool_d;
  const double default_step_down = std::min(kDefaultStepDownCapMm, 0.5 * tool_d);
  const double step_down = step_down_mm > kEps ? step_down_mm : default_step_down;
  const double step_over = std::max(kMinStepOverMm, step_over_mm);

  std::optional<ConvexPolygon> boundary = ConvexPolygon::try_from(outer_stripped);
  if (!boundary) {
    return Paths(1);
  }

  std::optional<ConvexPolygon> outermost = ConvexPolygon::try_from(inset(*boundary, tool_r));
  if (!outermost) {
    return Paths(1);
  }

  Paths paths(1);
  Path& moves = paths.front();
  moves.reserve(256);

  moves.push_back(make_comment(
      "pocket_spiral so=" + fmt3(step_over) + " sd=" + fmt3(step_down) +
      " depth=" + fmt3(std::abs(depth))));
  moves.push_back(make_set_rpm(tool.rpm));
  moves.push_back(make_set_feed(tool.feed_xy));

  std::vector<Polygon> rings;
  {
    Polygon ring = outermost->points();
    double accumulated_offset = 0.0;
    while (!ring.empty()) {
      rings.push_back(ring);
      accumulated_offset += step_over;
      ring = inset(*outermost, accumulated_offset);
    }
  }

  Vec2 sliver_a{}, sliver_b{};
  bool has_sliver = false;
  {
    const Polygon& last_ring = rings.back();
    Bounds lb = bounds_of(last_ring);
    double w = lb.maxx - lb.minx;
    double h = lb.maxy - lb.miny;
    double short_dim = std::min(w, h);
    double long_dim = std::max(w, h);
    if (long_dim > kEps && short_dim > tool_d + kEps) {
      double cx = 0.5 * (lb.minx + lb.maxx);
      double cy = 0.5 * (lb.miny + lb.maxy);
      if (w >= h) {
        sliver_a = {lb.minx, cy};
        sliver_b = {lb.maxx, cy};
      } else {
        sliver_a = {cx, lb.miny};
        sliver_b = {cx, lb.maxy};
      }
      has_sliver = true;
    }
  }

  const std::vector<double> z_levels = build_z_levels(depth, step_down);

  double prev_z = 0.0;
  for (double layer_z : z_levels) {
    const Polygon& first_ring = rings[0];
    size_t n0 = first_ring.size();
    size_t ramp_edge = longest_edge_index(first_ring);
    size_t ramp_start_idx = ramp_edge;
    size_t ramp_end_idx = (ramp_edge + 1) % n0;
    Vec2 ramp_path[2] = {first_ring[ramp_start_idx], first_ring[ramp_end_idx]};
    emit_ramp_or_plunge(moves, ramp_path, prev_z, layer_z,
                        ramp_angle_deg, safe_z, tool.feed_xy, tool.feed_z);
    moves.push_back(make_set_feed(tool.feed_xy));

    for (size_t ring_idx = 0; ring_idx < rings.size(); ++ring_idx) {
      const Polygon& ring = rings[ring_idx];
      size_t n = ring.size();

      size_t start_vertex = (ring_idx == 0) ? (ramp_end_idx + 1) % n : 0;

      bool has_next = (ring_idx + 1 < rings.size());

      if (!has_next) {
        for (size_t step = 0; step < n; ++step) {
          size_t vi = (start_vertex + step) % n;
          moves.push_back(make_cut(ring[vi].x, ring[vi].y, std::nullopt));
        }
        moves.push_back(make_cut(ring[start_vertex % n].x, ring[start_vertex % n].y, std::nullopt));
      } else {
        size_t edges_to_full = (ring_idx == 0) ? n - 1 : n;
        for (size_t step = 0; step < edges_to_full; ++step) {
          size_t vi = (start_vertex + step) % n;
          size_t vi_next = (start_vertex + step + 1) % n;

          bool is_last_edge = (step == edges_to_full - 1);
          if (!is_last_edge) {
            moves.push_back(make_cut(ring[vi_next].x, ring[vi_next].y, std::nullopt));
          } else {
            const Vec2& A = ring[vi];
            const Vec2& B = ring[vi_next];
            const Vec2& T = rings[ring_idx + 1][0];

            double dx = B.x - A.x;
            double dy = B.y - A.y;
            double len2 = dx * dx + dy * dy;
            double t_param = 0.0;
            if (len2 > kEps) {
              t_param = std::clamp(((T.x - A.x) * dx + (T.y - A.y) * dy) / len2, 0.0, 1.0);
            }
            Vec2 P = {A.x + t_param * dx, A.y + t_param * dy};
            moves.push_back(make_cut(P.x, P.y, std::nullopt));
            moves.push_back(make_cut(T.x, T.y, std::nullopt));
          }
        }
      }
    }

    if (has_sliver) {
      const Polygon& last_ring = rings.back();
      const Vec2& ring_end = last_ring[0];
      double da = std::hypot(sliver_a.x - ring_end.x, sliver_a.y - ring_end.y);
      double db = std::hypot(sliver_b.x - ring_end.x, sliver_b.y - ring_end.y);
      const Vec2& near = da <= db ? sliver_a : sliver_b;
      const Vec2& far  = da <= db ? sliver_b : sliver_a;
      moves.push_back(make_cut(near.x, near.y, std::nullopt));
      moves.push_back(make_cut(far.x, far.y, std::nullopt));
    }

    moves.push_back(make_retract(safe_z));
    prev_z = layer_z;
  }

  return paths;
}

}  // namespace

Paths plan_pocket(const PlanarFace& face, const Tool& tool, double step_over_mm, double step_down_mm,
                  double safe_z_mm, double ramp_angle_deg, PocketStrategy strategy) {
  Polygon outer = strip_closing_vertex(face.outer);
  if (strategy == PocketStrategy::Spiral && is_convex(outer)) {
    return plan_pocket_spiral(outer, tool, face.depth, step_over_mm, step_down_mm, safe_z_mm, ramp_angle_deg);
  }

  if (strategy == PocketStrategy::Spiral) {
    Paths paths = plan_pocket_raster_clipped(outer, tool, face.depth, step_over_mm, step_down_mm, safe_z_mm, ramp_angle_deg);
    if (!paths.empty() && !paths.front().empty()) {
      paths.front().insert(paths.front().begin(), make_comment("concave polygon: raster clipped to boundary"));
    }
    return paths;
  }

  return plan_pocket_raster(face, tool, step_over_mm, step_down_mm, safe_z_mm, ramp_angle_deg);
}

Paths plan_profile(const Polygon& boundary, const Tool& tool, double total_depth_mm, double step_down_mm,
                   double safe_z, double ramp_angle_deg) {
  const double depth_target = -std::abs(total_depth_mm);

  Paths paths(1);
  Path& moves = paths.front();
  moves.reserve(boundary.size() * 4);
  moves.push_back(make_comment("profile_outline"));
  moves.push_back(make_set_rpm(tool.rpm));
  moves.push_back(make_set_feed(tool.feed_xy));

  const double step_down = step_down_mm <= 0.0 ? kProfileDefaultStepDownMm : step_down_mm;

  bool closed = boundary.size() >= 2 &&
                std::abs(boundary.front().x - boundary.back().x) < kEps &&
                std::abs(boundary.front().y - boundary.back().y) < kEps;
  double use_ramp = (ramp_angle_deg > kEps && closed) ? ramp_angle_deg : 0.0;

  double z = 0.0;
  double prev_z = 0.0;
  while (z > depth_target) {
    z = std::max(z - step_down, depth_target);
    if (boundary.empty()) {
      break;
    }

    bool can_keepdown = use_ramp > kEps && std::abs(prev_z) > kEps;
    bool is_last_pass = std::max(z - step_down, depth_target) >= depth_target - kEps
                        && std::abs(z - depth_target) < kEps;

    if (use_ramp > kEps) {
      std::vector<Vec2> rev_path;
      rev_path.reserve(boundary.size());
      for (std::size_t i = boundary.size() - 1; i >= 1; --i) {
        rev_path.push_back(boundary[i]);
      }
      rev_path.push_back(boundary[0]);
      emit_ramp_or_plunge(moves, rev_path,
                          prev_z, z, use_ramp, safe_z, tool.feed_xy, tool.feed_z,
                          can_keepdown);
    } else {
      const Vec2& start = boundary.front();
      moves.push_back(make_rapid(start.x, start.y, safe_z));
      moves.push_back(make_cut(std::nullopt, std::nullopt, z, tool.feed_z));
    }

    moves.push_back(make_set_feed(tool.feed_xy));
    for (std::size_t i = 1; i < boundary.size(); ++i) {
      const Vec2& p = boundary[i];
      moves.push_back(make_cut(p.x, p.y, std::nullopt));
    }

    if (is_last_pass || !(use_ramp > kEps)) {
      moves.push_back(make_retract(safe_z));
    }
    prev_z = z;
  }

  return paths;
}

Paths plan_drill(const std::vector<Hole>& holes, const Tool& tool, double peck_mm, double safe_z,
                 double retract_clearance_mm) {
  Paths paths(1);
  Path& moves = paths.front();
  moves.reserve(holes.size() * 8);

  moves.push_back(make_comment("drill_peck"));
  moves.push_back(make_set_rpm(tool.rpm));
  moves.push_back(make_set_feed(tool.feed_z));

  const double peck = peck_mm <= 0.0 ? kDefaultPeckMm : peck_mm;
  const double r_plane = retract_clearance_mm;
  for (const auto& hole : holes) {
    moves.push_back(make_rapid(hole.x, hole.y, safe_z));
    double z = 0.0;
    const double depth = -std::abs(hole.depth);
    while (z > depth + kEps) {
      double z_next = std::max(depth, z - peck);
      moves.push_back(make_cut(std::nullopt, std::nullopt, z_next));
      z = z_next;
      if (std::abs(z - depth) < kEps) {
        break;
      }
      moves.push_back(make_cut(std::nullopt, std::nullopt, r_plane, tool.feed_z));
      double reentry_target = z + 1.0;
      double reentry_z = r_plane;
      constexpr double kMaxReentryStep = 25.0;
      while (reentry_z > reentry_target + kEps) {
        reentry_z = std::max(reentry_target, reentry_z - kMaxReentryStep);
        moves.push_back(make_cut(std::nullopt, std::nullopt, reentry_z, tool.feed_z));
      }
    }
    moves.push_back(make_retract(safe_z));
  }

  return paths;
}

Paths plan_bore_helical(const Hole& hole, const Tool& tool, double step_down_mm, double safe_z) {
  Paths paths(1);
  Path& moves = paths.front();

  const double tool_d = tool.diameter <= 0.0 ? kBoreDefaultToolDiameterMm : tool.diameter;
  const double D = hole.diameter;
  if (D <= tool_d) {
    return paths;
  }

  const double target = -std::abs(hole.depth);
  const double r_eff = std::max(0.01, (D - tool_d) * 0.5);
  const double step_down = step_down_mm <= 0.0 ? kBoreDefaultStepDownMm : step_down_mm;
  const int segments = kHelixSegments;

  moves.push_back(make_comment("bore_helical D=" + fmt3(D) + " tool=" + fmt3(tool_d) + " r_eff=" + fmt3(r_eff)));
  moves.push_back(make_set_rpm(tool.rpm));
  moves.push_back(make_set_feed(tool.feed_xy));
  moves.push_back(make_rapid(hole.x + r_eff, hole.y, safe_z));

  auto circle_point = [&](int i, double radius) {
    const double t = 2.0 * std::numbers::pi * (static_cast<double>(i) / segments);
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
      moves.push_back(make_cut(pt.x, pt.y, std::nullopt));
    }
  }

  moves.push_back(make_retract(safe_z));
  return paths;
}

}  // namespace millui::native::algo
