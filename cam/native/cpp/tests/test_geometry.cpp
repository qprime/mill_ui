#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include <doctest/doctest.h>

#include <cmath>

#include "millui/native/algo/geom2d.hpp"

using namespace millui::native;
using namespace millui::native::algo;

namespace {

bool near(double a, double b) { return std::abs(a - b) < 1e-9; }

Polygon square(double s) { return {{0.0, 0.0}, {s, 0.0}, {s, s}, {0.0, s}}; }

}  // namespace

TEST_CASE("build_z_levels descends exactly on an even multiple") {
    const std::vector<double> levels = build_z_levels(-6.0, 2.0);
    REQUIRE(levels.size() == 3);
    CHECK(near(levels[0], -2.0));
    CHECK(near(levels[1], -4.0));
    CHECK(near(levels[2], -6.0));
}

TEST_CASE("build_z_levels clamps the final level to depth without overshoot") {
    const std::vector<double> levels = build_z_levels(-5.0, 2.0);
    REQUIRE(levels.size() == 3);
    CHECK(near(levels[0], -2.0));
    CHECK(near(levels[1], -4.0));
    CHECK(near(levels[2], -5.0));
}

TEST_CASE("build_z_levels of zero depth yields no levels") {
    CHECK(build_z_levels(0.0, 2.0).empty());
}

TEST_CASE("ConvexPolygon::try_from rejects a reflex polygon") {
    const Polygon l_shape = {{0.0, 0.0}, {4.0, 0.0}, {4.0, 2.0},
                             {2.0, 2.0}, {2.0, 4.0}, {0.0, 4.0}};
    CHECK_FALSE(ConvexPolygon::try_from(l_shape).has_value());
}

TEST_CASE(
    "ConvexPolygon::try_from normalizes a CCW closed square to CW and strips the closing vertex") {
    Polygon ccw_closed = square(4.0);
    ccw_closed.push_back(ccw_closed.front());
    REQUIRE(ccw_closed.size() == 5);

    auto convex = ConvexPolygon::try_from(ccw_closed);
    REQUIRE(convex.has_value());

    const Polygon& pts = convex->points();
    CHECK(pts.size() == 4);
    CHECK(shoelace_area(pts) < 0.0);
}

TEST_CASE("inset collapse returns an empty polygon, not a degenerate one") {
    auto convex = ConvexPolygon::try_from(square(4.0));
    REQUIRE(convex.has_value());
    const Polygon result = inset(*convex, 2.0);
    CHECK(result.empty());
}

TEST_CASE("inset shrinks a convex polygon inward for a valid offset") {
    auto convex = ConvexPolygon::try_from(square(10.0));
    REQUIRE(convex.has_value());
    const Polygon result = inset(*convex, 2.0);
    REQUIRE(result.size() == 4);
    CHECK(std::abs(shoelace_area(result)) < std::abs(shoelace_area(convex->points())));
}

TEST_CASE("scanline_intersections skips horizontal edges yielding an even crossing count") {
    const Polygon poly = square(10.0);
    const std::vector<double> xs = scanline_intersections(poly, 5.0);
    REQUIRE(xs.size() == 2);
    CHECK(near(xs[0], 0.0));
    CHECK(near(xs[1], 10.0));
}
