#pragma once

#include <optional>
#include <string>
#include <variant>
#include <vector>

namespace millui::native {

template <class... Ts>
struct overloaded : Ts... {
    using Ts::operator()...;
};
template <class... Ts>
overloaded(Ts...) -> overloaded<Ts...>;

struct Vec2 {
    double x = 0.0;
    double y = 0.0;
};
using Polygon = std::vector<Vec2>;

struct PlanarFace {
    double depth = 0.0;
    double safe_z = 5.0;
    Polygon outer;
};

struct Hole {
    double x = 0.0;
    double y = 0.0;
    double diameter = 0.0;
    double depth = 0.0;
};

struct Tool {
    double diameter = 0.0;
    double rpm = 0.0;
    double feed_xy = 0.0;
    double feed_z = 0.0;
};

struct PostConfig {
    std::string unit;  // "mm" or "inch"
    double safe_z = 5.0;
    int prec = 3;
    std::vector<std::string> header;
    std::vector<std::string> footer;
};

struct Comment {
    std::string text;
};
struct SetRpm {
    double rpm = 0.0;
};
struct SetFeed {
    double feed = 0.0;
};
struct Rapid {
    std::optional<double> x;
    std::optional<double> y;
    std::optional<double> z;
};
struct Cut {
    std::optional<double> x;
    std::optional<double> y;
    std::optional<double> z;
    std::optional<double> feed;
};
struct Retract {
    double z = 0.0;
};
struct Dwell {
    double seconds = 0.0;
};

using Move = std::variant<Comment, SetRpm, SetFeed, Rapid, Cut, Retract, Dwell>;
using Path = std::vector<Move>;
using Paths = std::vector<Path>;

enum class PocketStrategy { Raster, Spiral };

}  // namespace millui::native
