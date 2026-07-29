#include "millui/native/algo/post_gcode.hpp"

#include <cmath>
#include <format>
#include <optional>
#include <sstream>
#include <vector>

#include "millui/native/algo/format.hpp"
#include "millui/native/algo/geom2d.hpp"

namespace millui::native::algo {

namespace {

std::string rpm_line(double rpm) { return std::format("M3 S{}", std::lround(rpm)); }

std::vector<std::string> default_header(const PostConfig& cfg) {
    std::vector<std::string> header{"(begin)", "G90", "G21", "G17", "G94"};
    if (cfg.unit == "inch") {
        header[2] = "G20";
    }
    return header;
}

std::vector<std::string> default_footer() { return {"M5", "M2", "(end)"}; }

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
                            if (ch == '(') {
                                ch = '[';
                            }
                            if (ch == ')') {
                                ch = ']';
                            }
                        }
                        lines.emplace_back("(" + text + ")");
                    },
                    [&](const SetRpm& s) {
                        if (current_rpm && std::abs(*current_rpm - s.rpm) < kEps) {
                            return;
                        }
                        current_rpm = s.rpm;
                        lines.emplace_back(rpm_line(s.rpm));
                    },
                    [&](const SetFeed& s) {
                        if (current_feed && std::abs(*current_feed - s.feed) < kEps) {
                            return;
                        }
                        current_feed = s.feed;
                        lines.emplace_back("F" + format_fixed(s.feed, feed_precision(cfg.prec)));
                    },
                    [&](const Rapid& r) {
                        lines.emplace_back(
                            format_motion("G0", {.x = r.x, .y = r.y, .z = r.z}, cfg.prec));
                        if (r.z) {
                            current_z = r.z;
                        }
                    },
                    [&](const Cut& c) {
                        const std::optional<double> feed = c.feed ? c.feed : current_feed;
                        lines.emplace_back(format_motion(
                            "G1", {.x = c.x, .y = c.y, .z = c.z, .feed = feed}, cfg.prec));
                        if (c.z) {
                            current_z = c.z;
                        }
                        if (c.feed) {
                            current_feed = c.feed;
                        }
                    },
                    [&](const Retract& r) {
                        const double z = r.z;
                        lines.emplace_back(format_motion("G0", {.z = z}, cfg.prec));
                        current_z = z;
                    },
                    [&](const Dwell& d) {
                        if (d.seconds > 0.0) {
                            lines.emplace_back("G4 P" + format_fixed(d.seconds, cfg.prec));
                        }
                    },
                },
                move);
        }
    }

    if (!current_z || std::abs(*current_z - cfg.safe_z) > kEps) {
        lines.emplace_back(format_motion("G0", {.z = cfg.safe_z}, cfg.prec));
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
