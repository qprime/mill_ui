#include "millui/native/algo/post_gcode.hpp"

#include <cmath>
#include <limits>
#include <sstream>
#include <vector>

namespace millui::native::algo {

namespace {

bool has(double v) {
  return !std::isnan(v);
}

std::string fmt_num(double v, int prec) {
  std::ostringstream oss;
  oss.setf(std::ios::fixed, std::ios::floatfield);
  oss.precision(prec);
  oss << v;
  return oss.str();
}

std::string g0(double x, double y, double z, int prec) {
  std::vector<std::string> parts{"G0"};
  if (has(x)) parts.emplace_back("X" + fmt_num(x, prec));
  if (has(y)) parts.emplace_back("Y" + fmt_num(y, prec));
  if (has(z)) parts.emplace_back("Z" + fmt_num(z, prec));
  std::ostringstream oss;
  for (std::size_t i = 0; i < parts.size(); ++i) {
    if (i) oss << ' ';
    oss << parts[i];
  }
  return oss.str();
}

std::string g1(double x, double y, double z, double feed, int prec) {
  std::vector<std::string> parts{"G1"};
  if (has(x)) parts.emplace_back("X" + fmt_num(x, prec));
  if (has(y)) parts.emplace_back("Y" + fmt_num(y, prec));
  if (has(z)) parts.emplace_back("Z" + fmt_num(z, prec));
  if (has(feed)) {
    const int feed_prec = std::max(0, prec - 2);
    parts.emplace_back("F" + fmt_num(feed, feed_prec));
  }
  std::ostringstream oss;
  for (std::size_t i = 0; i < parts.size(); ++i) {
    if (i) oss << ' ';
    oss << parts[i];
  }
  return oss.str();
}

std::string rpm_line(double rpm) {
  if (!has(rpm)) {
    return {};
  }
  std::ostringstream oss;
  oss << "M3 S" << static_cast<int>(std::lround(rpm));
  return oss.str();
}

std::vector<std::string> default_header(const PostConfig& cfg) {
  std::vector<std::string> header{"(begin)", "G90", "G21", "G17", "G94"};
  if (cfg.unit == "inch") {
    header[2] = "G20";
  }
  return header;
}

std::vector<std::string> default_footer() {
  return {"M5", "M2", "(end)"};
}

}  // namespace

std::string post_gcode(const Paths& paths, const PostConfig& cfg) {
  std::vector<std::string> lines = cfg.header.empty() ? default_header(cfg) : cfg.header;
  double current_feed = std::numeric_limits<double>::quiet_NaN();
  double current_rpm = std::numeric_limits<double>::quiet_NaN();
  double current_z = std::numeric_limits<double>::quiet_NaN();

  for (const auto& path : paths) {
    for (const auto& move : path) {
      if (move.kind == "comment") {
        std::string text = move.text;
        for (char& c : text) {
          if (c == '(') c = '[';
          if (c == ')') c = ']';
        }
        lines.emplace_back("(" + text + ")");
      } else if (move.kind == "set_rpm") {
        if (!has(move.rpm) || (has(current_rpm) && std::abs(current_rpm - move.rpm) < 1e-9)) {
          continue;
        }
        current_rpm = move.rpm;
        const std::string ln = rpm_line(move.rpm);
        if (!ln.empty()) {
          lines.emplace_back(ln);
        }
      } else if (move.kind == "set_feed") {
        if (!has(move.feed) || (has(current_feed) && std::abs(current_feed - move.feed) < 1e-9)) {
          continue;
        }
        current_feed = move.feed;
        const int feed_prec = std::max(0, cfg.prec - 2);
        lines.emplace_back("F" + fmt_num(move.feed, feed_prec));
      } else if (move.kind == "rapid") {
        lines.emplace_back(g0(move.x, move.y, move.z, cfg.prec));
        if (has(move.z)) {
          current_z = move.z;
        }
      } else if (move.kind == "cut") {
        const double feed = has(move.feed) ? move.feed : current_feed;
        lines.emplace_back(g1(move.x, move.y, move.z, feed, cfg.prec));
        if (has(move.z)) {
          current_z = move.z;
        }
        if (has(move.feed)) {
          current_feed = move.feed;
        }
      } else if (move.kind == "retract") {
        const double z = has(move.z) ? move.z : cfg.safe_z;
        lines.emplace_back(g0(std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::quiet_NaN(), z, cfg.prec));
        current_z = z;
      } else {
        lines.emplace_back("(unhandled move kind: " + move.kind + ")");
      }
    }
  }

  if (!has(current_z) || std::abs(current_z - cfg.safe_z) > 1e-9) {
    lines.emplace_back(g0(std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::quiet_NaN(), cfg.safe_z, cfg.prec));
  }

  const auto footer = cfg.footer.empty() ? default_footer() : cfg.footer;
  lines.insert(lines.end(), footer.begin(), footer.end());

  std::ostringstream oss;
  for (const auto& line : lines) {
    oss << line << '\n';
  }
  return oss.str();
}

}  // namespace millui::native::algo
