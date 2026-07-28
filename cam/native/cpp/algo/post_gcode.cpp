#include "millui/native/algo/post_gcode.hpp"

#include <cmath>
#include <optional>
#include <sstream>
#include <vector>

namespace millui::native::algo {

namespace {

template <class... Ts>
struct overloaded : Ts... {
  using Ts::operator()...;
};
template <class... Ts>
overloaded(Ts...) -> overloaded<Ts...>;

std::string fmt_num(double v, int prec) {
  std::ostringstream oss;
  oss.setf(std::ios::fixed, std::ios::floatfield);
  oss.precision(prec);
  oss << v;
  return oss.str();
}

std::string g0(std::optional<double> x, std::optional<double> y, std::optional<double> z, int prec) {
  std::vector<std::string> parts{"G0"};
  if (x) parts.emplace_back("X" + fmt_num(*x, prec));
  if (y) parts.emplace_back("Y" + fmt_num(*y, prec));
  if (z) parts.emplace_back("Z" + fmt_num(*z, prec));
  std::ostringstream oss;
  for (std::size_t i = 0; i < parts.size(); ++i) {
    if (i) oss << ' ';
    oss << parts[i];
  }
  return oss.str();
}

std::string g1(std::optional<double> x, std::optional<double> y, std::optional<double> z,
               std::optional<double> feed, int prec) {
  std::vector<std::string> parts{"G1"};
  if (x) parts.emplace_back("X" + fmt_num(*x, prec));
  if (y) parts.emplace_back("Y" + fmt_num(*y, prec));
  if (z) parts.emplace_back("Z" + fmt_num(*z, prec));
  if (feed) {
    const int feed_prec = std::max(0, prec - 2);
    parts.emplace_back("F" + fmt_num(*feed, feed_prec));
  }
  std::ostringstream oss;
  for (std::size_t i = 0; i < parts.size(); ++i) {
    if (i) oss << ' ';
    oss << parts[i];
  }
  return oss.str();
}

std::string rpm_line(double rpm) {
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
  std::optional<double> current_feed;
  std::optional<double> current_rpm;
  std::optional<double> current_z;

  for (const auto& path : paths) {
    for (const auto& move : path) {
      std::visit(
          overloaded{
              [&](const Comment& c) {
                std::string text = c.text;
                for (char& ch : text) {
                  if (ch == '(') ch = '[';
                  if (ch == ')') ch = ']';
                }
                lines.emplace_back("(" + text + ")");
              },
              [&](const SetRpm& s) {
                if (current_rpm && std::abs(*current_rpm - s.rpm) < 1e-9) {
                  return;
                }
                current_rpm = s.rpm;
                lines.emplace_back(rpm_line(s.rpm));
              },
              [&](const SetFeed& s) {
                if (current_feed && std::abs(*current_feed - s.feed) < 1e-9) {
                  return;
                }
                current_feed = s.feed;
                const int feed_prec = std::max(0, cfg.prec - 2);
                lines.emplace_back("F" + fmt_num(s.feed, feed_prec));
              },
              [&](const Rapid& r) {
                lines.emplace_back(g0(r.x, r.y, r.z, cfg.prec));
                if (r.z) {
                  current_z = *r.z;
                }
              },
              [&](const Cut& c) {
                const std::optional<double> feed = c.feed ? c.feed : current_feed;
                lines.emplace_back(g1(c.x, c.y, c.z, feed, cfg.prec));
                if (c.z) {
                  current_z = *c.z;
                }
                if (c.feed) {
                  current_feed = *c.feed;
                }
              },
              [&](const Retract& r) {
                const double z = r.z.value_or(cfg.safe_z);
                lines.emplace_back(g0(std::nullopt, std::nullopt, z, cfg.prec));
                current_z = z;
              },
              [&](const Dwell& d) {
                if (d.seconds > 0.0) {
                  lines.emplace_back("G4 P" + fmt_num(d.seconds, cfg.prec));
                }
              },
          },
          move);
    }
  }

  if (!current_z || std::abs(*current_z - cfg.safe_z) > 1e-9) {
    lines.emplace_back(g0(std::nullopt, std::nullopt, cfg.safe_z, cfg.prec));
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
