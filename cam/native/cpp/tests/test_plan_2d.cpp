#include <doctest/doctest.h>

#include <array>
#include <cmath>
#include <optional>
#include <span>
#include <string>
#include <variant>
#include <vector>

#include "millui/native/algo/geom2d.hpp"
#include "millui/native/algo/plan_2d.hpp"
#include "millui/native/types.hpp"

using namespace millui::native;
using namespace millui::native::algo;

namespace {

bool near(double a, double b) { return std::abs(a - b) < 1e-9; }

Polygon square(double s) { return {{0.0, 0.0}, {s, 0.0}, {s, s}, {0.0, s}}; }

Tool make_tool(double diameter) { return Tool{diameter, 12000.0, 1000.0, 300.0}; }

bool has_comment(const Path& moves, const std::string& needle) {
    for (const auto& mv : moves) {
        if (const auto* c = std::get_if<Comment>(&mv)) {
            if (c->text.find(needle) != std::string::npos) {
                return true;
            }
        }
    }
    return false;
}

}  // namespace

TEST_CASE("emit_ramp_or_plunge descends monotonically across a multi-segment ramp") {
    Path moves;
    const std::array<Vec2, 3> path = {Vec2{0.0, 0.0}, Vec2{50.0, 0.0}, Vec2{50.0, 50.0}};
    emit_ramp_or_plunge(moves, path, 0.0, -2.0, 30.0, 5.0, 1000.0, 300.0);

    double prev_z = 0.0;
    int cuts_with_z = 0;
    for (const auto& mv : moves) {
        const auto* cut = std::get_if<Cut>(&mv);
        if (cut == nullptr || !cut->z) {
            continue;
        }
        CHECK(*cut->z <= prev_z + 1e-9);
        prev_z = *cut->z;
        ++cuts_with_z;
    }
    CHECK(cuts_with_z > 1);
    CHECK(near(prev_z, -2.0));
}

TEST_CASE("emit_ramp_or_plunge falls back to a plunge when the path is shorter than the ramp") {
    Path moves;
    const std::array<Vec2, 2> path = {Vec2{0.0, 0.0}, Vec2{0.5, 0.0}};
    emit_ramp_or_plunge(moves, path, 0.0, -5.0, 30.0, 5.0, 1000.0, 300.0);

    CHECK(has_comment(moves, "ramp fallback"));
    const auto* last = std::get_if<Cut>(&moves.back());
    REQUIRE(last != nullptr);
    REQUIRE(last->z.has_value());
    CHECK(near(*last->z, -5.0));
    CHECK_FALSE(last->x.has_value());
}

TEST_CASE("emit_ramp_or_plunge on an empty path emits nothing") {
    Path moves;
    emit_ramp_or_plunge(moves, std::span<const Vec2>{}, 0.0, -2.0, 30.0, 5.0, 1000.0, 300.0);
    CHECK(moves.empty());
}

TEST_CASE("build_inset_rings terminates at the minimum step over on a large pocket") {
    auto convex = ConvexPolygon::try_from(square(500.0));
    REQUIRE(convex.has_value());

    const std::vector<Polygon> rings = build_inset_rings(*convex, kMinStepOverMm);
    CHECK_FALSE(rings.empty());
    CHECK(rings.size() == 2500);
}

TEST_CASE("build_inset_rings shrinks each ring strictly inside the previous") {
    auto convex = ConvexPolygon::try_from(square(100.0));
    REQUIRE(convex.has_value());

    const std::vector<Polygon> rings = build_inset_rings(*convex, 5.0);
    REQUIRE(rings.size() > 2);
    for (std::size_t i = 1; i < rings.size(); ++i) {
        CHECK(std::abs(shoelace_area(rings[i])) < std::abs(shoelace_area(rings[i - 1])));
    }
}

TEST_CASE("build_inset_rings yields a single ring when the first inset collapses") {
    auto convex = ConvexPolygon::try_from(square(4.0));
    REQUIRE(convex.has_value());

    const std::vector<Polygon> rings = build_inset_rings(*convex, 2.0);
    CHECK(rings.size() == 1);
}

TEST_CASE("find_sliver_span spans x at mid height on a wide ring") {
    const Polygon wide = {{0.0, 0.0}, {40.0, 0.0}, {40.0, 10.0}, {0.0, 10.0}};
    const auto span = find_sliver_span(wide, 3.0);
    REQUIRE(span.has_value());
    CHECK(near(span->first.x, 0.0));
    CHECK(near(span->second.x, 40.0));
    CHECK(near(span->first.y, 5.0));
    CHECK(near(span->second.y, 5.0));
}

TEST_CASE("find_sliver_span spans y at mid width on a tall ring") {
    const Polygon tall = {{0.0, 0.0}, {10.0, 0.0}, {10.0, 40.0}, {0.0, 40.0}};
    const auto span = find_sliver_span(tall, 3.0);
    REQUIRE(span.has_value());
    CHECK(near(span->first.y, 0.0));
    CHECK(near(span->second.y, 40.0));
    CHECK(near(span->first.x, 5.0));
    CHECK(near(span->second.x, 5.0));
}

TEST_CASE("find_sliver_span yields nothing on a ring narrower than the tool") {
    const Polygon narrow = {{0.0, 0.0}, {40.0, 0.0}, {40.0, 2.0}, {0.0, 2.0}};
    CHECK_FALSE(find_sliver_span(narrow, 3.0).has_value());
}

TEST_CASE("PocketParams::resolve substitutes the default diameter for a zero-diameter tool") {
    const PocketParams params = PocketParams::resolve(make_tool(0.0), 6.0, 2.0, 1.0);
    CHECK(near(params.tool_diameter, kDefaultToolDiameterMm));
    CHECK(near(params.tool_radius, 0.5 * kDefaultToolDiameterMm));
    CHECK(near(params.depth, -6.0));
}

TEST_CASE("PocketParams::resolve defaults step down to half the tool, capped") {
    const PocketParams small = PocketParams::resolve(make_tool(4.0), 6.0, 2.0, 0.0);
    CHECK(near(small.step_down, 2.0));

    const PocketParams large = PocketParams::resolve(make_tool(20.0), 6.0, 2.0, 0.0);
    CHECK(near(large.step_down, kDefaultStepDownCapMm));
}

TEST_CASE("PocketParams::resolve floors step over at the minimum") {
    const PocketParams params = PocketParams::resolve(make_tool(6.0), 6.0, 0.0, 1.0);
    CHECK(near(params.step_over, kMinStepOverMm));
}

TEST_CASE("plan_pocket spiral ends at safe z") {
    PlanarFace face;
    face.depth = 4.0;
    face.safe_z = 5.0;
    face.outer = square(60.0);

    const Paths paths =
        plan_pocket(face, make_tool(6.0), 3.0, 2.0, face.safe_z, 0.0, PocketStrategy::Spiral);
    REQUIRE(paths.size() == 1);
    REQUIRE_FALSE(paths.front().empty());

    const auto* last = std::get_if<Retract>(&paths.front().back());
    REQUIRE(last != nullptr);
    REQUIRE(last->z.has_value());
    CHECK(near(*last->z, 5.0));
}

TEST_CASE("plan_pocket falls back to clipped raster on a concave polygon") {
    PlanarFace face;
    face.depth = 4.0;
    face.safe_z = 5.0;
    face.outer = {{0.0, 0.0}, {60.0, 0.0}, {60.0, 30.0}, {30.0, 30.0}, {30.0, 60.0}, {0.0, 60.0}};

    const Paths paths =
        plan_pocket(face, make_tool(6.0), 3.0, 2.0, face.safe_z, 0.0, PocketStrategy::Spiral);
    REQUIRE(paths.size() == 1);
    CHECK(has_comment(paths.front(), "concave polygon: raster clipped"));
}
