#include <doctest/doctest.h>

#include <string>

#include "millui/native/algo/post_gcode.hpp"
#include "millui/native/types.hpp"

using namespace millui::native;
using namespace millui::native::algo;

namespace {

bool contains(const std::string& haystack, const std::string& needle) {
    return haystack.find(needle) != std::string::npos;
}

int count_occurrences(const std::string& haystack, const std::string& needle) {
    int count = 0;
    std::size_t pos = 0;
    while ((pos = haystack.find(needle, pos)) != std::string::npos) {
        ++count;
        pos += needle.size();
    }
    return count;
}

PostConfig default_cfg() {
    PostConfig cfg;
    cfg.unit = "mm";
    cfg.safe_z = 5.0;
    cfg.prec = 3;
    return cfg;
}

}  // namespace

TEST_CASE("a repeated feed emits a single F line") {
    Paths paths{{SetFeed{1200.0}, SetFeed{1200.0}}};
    const std::string g = post_gcode(paths, default_cfg());
    CHECK(count_occurrences(g, "F1200.0") == 1);
}

TEST_CASE("comment parentheses are sanitized to brackets") {
    Paths paths{{Comment{"a(b)c"}}};
    const std::string g = post_gcode(paths, default_cfg());
    CHECK(contains(g, "(a[b]c)"));
}

TEST_CASE("inch unit swaps G21 for G20 in the default header") {
    PostConfig cfg = default_cfg();
    cfg.unit = "inch";
    const std::string g = post_gcode(Paths{}, cfg);
    CHECK(contains(g, "G20"));
    CHECK_FALSE(contains(g, "G21"));
}

TEST_CASE("mm unit keeps G21 in the default header") {
    const std::string g = post_gcode(Paths{}, default_cfg());
    CHECK(contains(g, "G21"));
    CHECK_FALSE(contains(g, "G20"));
}

TEST_CASE("a cut with absent axes emits only the present axes") {
    Paths paths{{Cut{std::nullopt, std::nullopt, -3.0, 800.0}}};
    const std::string g = post_gcode(paths, default_cfg());
    CHECK(contains(g, "G1 Z-3.000 F800.0"));
}

TEST_CASE("a retract emits only Z at the given height") {
    Paths paths{{Retract{6.0}}};
    const std::string g = post_gcode(paths, default_cfg());
    CHECK(contains(g, "G0 Z6.000"));
}

TEST_CASE("a retract with absent Z falls back to the configured safe height") {
    Paths paths{{Retract{std::nullopt}}};
    const std::string g = post_gcode(paths, default_cfg());
    CHECK(contains(g, "G0 Z5.000"));
}
