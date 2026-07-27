#pragma once

#include <limits>
#include <string>
#include <vector>

namespace millui::native {

constexpr double kToleranceMm = 0.01;

struct Vec2 {
  double x = 0.0;
  double y = 0.0;
};
using Polygon = std::vector<Vec2>;

struct PlanarFace {
  double z = 0.0;
  double depth = 0.0;
  double safe_z = 5.0;
  Polygon outer;
  std::vector<Polygon> holes;
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
  std::string kind;
};

struct PostConfig {
  std::string unit;  // "mm" or "inch"
  double safe_z = 5.0;
  int prec = 3;
  std::vector<std::string> header;
  std::vector<std::string> footer;
};

struct PathMove {
  std::string kind;  // comment|set_rpm|set_feed|rapid|cut|retract|dwell
  double x = std::numeric_limits<double>::quiet_NaN();
  double y = std::numeric_limits<double>::quiet_NaN();
  double z = std::numeric_limits<double>::quiet_NaN();
  double feed = std::numeric_limits<double>::quiet_NaN();
  double rpm = std::numeric_limits<double>::quiet_NaN();
  double seconds = std::numeric_limits<double>::quiet_NaN();
  std::string text;
};
using Path = std::vector<PathMove>;
using Paths = std::vector<Path>;

enum class PocketStrategy { Raster, Spiral };

}  // namespace millui::native
