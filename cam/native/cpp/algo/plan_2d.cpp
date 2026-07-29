#include "millui/native/algo/plan_2d.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <numbers>
#include <optional>
#include <span>
#include <sstream>
#include <vector>

#include "millui/native/algo/format.hpp"
#include "millui/native/algo/geom2d.hpp"

namespace millui::native::algo {

namespace {

constexpr double kDefaultPeckMm = 3.0;
constexpr double kProfileDefaultStepDownMm = 2.0;
constexpr double kBoreDefaultToolDiameterMm = 1.0;
constexpr double kBoreDefaultStepDownMm = 2.5;
constexpr int kHelixSegments = 60;
constexpr int kCommentPrecision = 3;

Move make_comment(std::string text) { return Comment{std::move(text)}; }

Move make_set_rpm(double rpm) { return SetRpm{rpm}; }

Move make_set_feed(double feed) { return SetFeed{feed}; }

Move make_rapid(double x, double y, double z) {
    return Rapid{x, y, z};  // planners always pass concrete axes; optionals fill from doubles
}

Move make_cut(std::optional<double> x, std::optional<double> y, std::optional<double> z,
              std::optional<double> feed = std::nullopt) {
    return Cut{x, y, z, feed};
}

Move make_retract(double z) { return Retract{z}; }

}  // namespace

PocketParams PocketParams::resolve(const Tool& tool, double depth_mm, double step_over_mm,
                                   double step_down_mm) {
    const double tool_d = tool.diameter <= 0.0 ? kDefaultToolDiameterMm : tool.diameter;
    const double default_step_down = std::min(kDefaultStepDownCapMm, 0.5 * tool_d);
    return PocketParams{
        .tool_diameter = tool_d,
        .tool_radius = 0.5 * tool_d,
        .step_down = step_down_mm > kEps ? step_down_mm : default_step_down,
        .step_over = std::max(kMinStepOverMm, step_over_mm),
        .depth = -std::abs(depth_mm),
    };
}

std::vector<Polygon> build_inset_rings(const ConvexPolygon& outermost, double step_over) {
    std::vector<Polygon> rings;
    Polygon ring = outermost.points();
    double accumulated_offset = 0.0;
    while (!ring.empty()) {
        rings.push_back(ring);
        accumulated_offset += step_over;
        ring = inset(outermost, accumulated_offset);
    }
    return rings;
}

std::optional<std::pair<Vec2, Vec2>> find_sliver_span(const Polygon& last_ring,
                                                      double tool_diameter) {
    const Bounds lb = bounds_of(last_ring);
    const double w = lb.maxx - lb.minx;
    const double h = lb.maxy - lb.miny;
    if (std::max(w, h) <= kEps || std::min(w, h) <= tool_diameter + kEps) {
        return std::nullopt;
    }
    if (w >= h) {
        const double cy = 0.5 * (lb.miny + lb.maxy);
        return std::pair{Vec2{lb.minx, cy}, Vec2{lb.maxx, cy}};
    }
    const double cx = 0.5 * (lb.minx + lb.maxx);
    return std::pair{Vec2{cx, lb.miny}, Vec2{cx, lb.maxy}};
}

void emit_ramp_or_plunge(Path& moves, std::span<const Vec2> path, double prev_z, double target_z,
                         double ramp_angle_deg, double safe_z, double feed_xy, double feed_z,
                         bool keepdown) {
    if (path.empty()) {
        return;
    }

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
        if (sl < kEps) {
            continue;
        }
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

namespace {

Paths plan_pocket_raster_clipped(const Polygon& outer_stripped, const Tool& tool,
                                 const PocketParams& params, double safe_z_mm,
                                 double ramp_angle_deg) {
    Polygon poly = ensure_cw(outer_stripped);
    const Bounds b = bounds_of(poly);
    const double safe_z = safe_z_mm;
    const double depth = params.depth;
    const double tool_r = params.tool_radius;
    const double step_down = params.step_down;
    const double step_over = params.step_over;

    Paths paths(1);
    Path& moves = paths.front();
    moves.reserve(128);

    moves.push_back(
        make_comment("pocket_raster_clipped so=" + format_fixed(step_over, kCommentPrecision) +
                     " sd=" + format_fixed(step_down, kCommentPrecision) +
                     " depth=" + format_fixed(std::abs(depth), kCommentPrecision)));
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
                if (x_right < x_left + kEps) {
                    continue;
                }

                double x_start = direction == 1 ? x_left : x_right;
                double x_end = direction == 1 ? x_right : x_left;

                if (std::abs(prev_z - layer_z) < kEps) {
                    moves.push_back(make_rapid(x_start, y, safe_z));
                    moves.push_back(make_cut(std::nullopt, std::nullopt, layer_z, tool.feed_z));
                } else {
                    const std::array<Vec2, 2> ramp_path = {Vec2{x_start, y}, Vec2{x_end, y}};
                    emit_ramp_or_plunge(moves, ramp_path, prev_z, layer_z, ramp_angle_deg, safe_z,
                                        tool.feed_xy, tool.feed_z);
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

Paths plan_pocket_raster(const PlanarFace& face, const Tool& tool, const PocketParams& params,
                         double safe_z_mm, double ramp_angle_deg) {
    const Bounds b = bounds_of(face.outer);
    const double safe_z = safe_z_mm;
    const double depth = params.depth;
    const double step_down = params.step_down;
    const double step_over = params.step_over;

    Paths paths(1);
    Path& moves = paths.front();
    moves.reserve(64);

    moves.push_back(make_comment("pocket_raster so=" + format_fixed(step_over, kCommentPrecision) +
                                 " sd=" + format_fixed(step_down, kCommentPrecision) +
                                 " depth=" + format_fixed(std::abs(depth), kCommentPrecision)));
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
            const std::array<Vec2, 2> ramp_path = {Vec2{x_start, y}, Vec2{x_end, y}};
            emit_ramp_or_plunge(moves, ramp_path, prev_z, layer_z, ramp_angle_deg, safe_z,
                                tool.feed_xy, tool.feed_z);
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

Paths plan_pocket_spiral(const Polygon& outer_stripped, const Tool& tool,
                         const PocketParams& params, double safe_z_mm, double ramp_angle_deg) {
    const double safe_z = safe_z_mm;
    const double depth = params.depth;
    const double step_down = params.step_down;
    const double step_over = params.step_over;

    std::optional<ConvexPolygon> boundary = ConvexPolygon::try_from(outer_stripped);
    if (!boundary) {
        return Paths(1);
    }

    std::optional<ConvexPolygon> outermost =
        ConvexPolygon::try_from(inset(*boundary, params.tool_radius));
    if (!outermost) {
        return Paths(1);
    }

    Paths paths(1);
    Path& moves = paths.front();
    moves.reserve(256);

    moves.push_back(make_comment("pocket_spiral so=" + format_fixed(step_over, kCommentPrecision) +
                                 " sd=" + format_fixed(step_down, kCommentPrecision) +
                                 " depth=" + format_fixed(std::abs(depth), kCommentPrecision)));
    moves.push_back(make_set_rpm(tool.rpm));
    moves.push_back(make_set_feed(tool.feed_xy));

    const std::vector<Polygon> rings = build_inset_rings(*outermost, step_over);
    const std::optional<std::pair<Vec2, Vec2>> sliver =
        find_sliver_span(rings.back(), params.tool_diameter);

    const std::vector<double> z_levels = build_z_levels(depth, step_down);

    double prev_z = 0.0;
    for (double layer_z : z_levels) {
        const Polygon& first_ring = rings[0];
        size_t n0 = first_ring.size();
        size_t ramp_edge = longest_edge_index(first_ring);
        size_t ramp_start_idx = ramp_edge;
        size_t ramp_end_idx = (ramp_edge + 1) % n0;
        const std::array<Vec2, 2> ramp_path = {first_ring[ramp_start_idx],
                                               first_ring[ramp_end_idx]};
        emit_ramp_or_plunge(moves, ramp_path, prev_z, layer_z, ramp_angle_deg, safe_z, tool.feed_xy,
                            tool.feed_z);
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
                moves.push_back(
                    make_cut(ring[start_vertex % n].x, ring[start_vertex % n].y, std::nullopt));
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
                            t_param =
                                std::clamp(((T.x - A.x) * dx + (T.y - A.y) * dy) / len2, 0.0, 1.0);
                        }
                        Vec2 P = {A.x + t_param * dx, A.y + t_param * dy};
                        moves.push_back(make_cut(P.x, P.y, std::nullopt));
                        moves.push_back(make_cut(T.x, T.y, std::nullopt));
                    }
                }
            }
        }

        if (sliver) {
            const Polygon& last_ring = rings.back();
            const Vec2& ring_end = last_ring[0];
            double da = std::hypot(sliver->first.x - ring_end.x, sliver->first.y - ring_end.y);
            double db = std::hypot(sliver->second.x - ring_end.x, sliver->second.y - ring_end.y);
            const Vec2& near = da <= db ? sliver->first : sliver->second;
            const Vec2& far = da <= db ? sliver->second : sliver->first;
            moves.push_back(make_cut(near.x, near.y, std::nullopt));
            moves.push_back(make_cut(far.x, far.y, std::nullopt));
        }

        moves.push_back(make_retract(safe_z));
        prev_z = layer_z;
    }

    return paths;
}

}  // namespace

Paths plan_pocket(const PlanarFace& face, const Tool& tool, double step_over_mm,
                  double step_down_mm, double safe_z_mm, double ramp_angle_deg,
                  PocketStrategy strategy) {
    Polygon outer = strip_closing_vertex(face.outer);
    const PocketParams params = PocketParams::resolve(tool, face.depth, step_over_mm, step_down_mm);

    if (strategy == PocketStrategy::Spiral && is_convex(outer)) {
        return plan_pocket_spiral(outer, tool, params, safe_z_mm, ramp_angle_deg);
    }

    if (strategy == PocketStrategy::Spiral) {
        Paths paths = plan_pocket_raster_clipped(outer, tool, params, safe_z_mm, ramp_angle_deg);
        if (!paths.empty() && !paths.front().empty()) {
            paths.front().insert(paths.front().begin(),
                                 make_comment("concave polygon: raster clipped to boundary"));
        }
        return paths;
    }

    return plan_pocket_raster(face, tool, params, safe_z_mm, ramp_angle_deg);
}

Paths plan_profile(const Polygon& boundary, const Tool& tool, double total_depth_mm,
                   double step_down_mm, double safe_z, double ramp_angle_deg) {
    const double depth_target = -std::abs(total_depth_mm);

    Paths paths(1);
    Path& moves = paths.front();
    moves.reserve(boundary.size() * 4);
    moves.push_back(make_comment("profile_outline"));
    moves.push_back(make_set_rpm(tool.rpm));
    moves.push_back(make_set_feed(tool.feed_xy));

    const double step_down = step_down_mm <= 0.0 ? kProfileDefaultStepDownMm : step_down_mm;

    bool closed = boundary.size() >= 2 && std::abs(boundary.front().x - boundary.back().x) < kEps &&
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
        bool is_last_pass = std::abs(z - depth_target) < kEps;

        if (use_ramp > kEps) {
            std::vector<Vec2> rev_path;
            rev_path.reserve(boundary.size());
            for (std::size_t i = boundary.size() - 1; i >= 1; --i) {
                rev_path.push_back(boundary[i]);
            }
            rev_path.push_back(boundary[0]);
            emit_ramp_or_plunge(moves, rev_path, prev_z, z, use_ramp, safe_z, tool.feed_xy,
                                tool.feed_z, can_keepdown);
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

    moves.push_back(make_comment("bore_helical D=" + format_fixed(D, kCommentPrecision) +
                                 " tool=" + format_fixed(tool_d, kCommentPrecision) +
                                 " r_eff=" + format_fixed(r_eff, kCommentPrecision)));
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
