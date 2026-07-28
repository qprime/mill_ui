#include "millui/native/algo/geom2d.hpp"

#include <algorithm>
#include <cmath>

namespace millui::native::algo {

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

double seg_length(const Vec2& a, const Vec2& b) { return std::hypot(b.x - a.x, b.y - a.y); }

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
    if (poly.size() >= 2 && std::abs(poly.front().x - poly.back().x) < kEps &&
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
        edges[i] = {{poly[i].x + sx, poly[i].y + sy}, {poly[j].x + sx, poly[j].y + sy}};
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

std::optional<ConvexPolygon> ConvexPolygon::try_from(const Polygon& poly) {
    Polygon p = ensure_cw(strip_closing_vertex(poly));
    if (!is_convex(p)) {
        return std::nullopt;
    }
    return ConvexPolygon(std::move(p));
}

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

}  // namespace millui::native::algo
