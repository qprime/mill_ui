#include "millui/native/algo/format.hpp"

#include <cstddef>
#include <format>
#include <sstream>
#include <vector>

namespace millui::native::algo {

std::string format_fixed(double v, int precision) { return std::format("{:.{}f}", v, precision); }

std::string format_compact(double v) { return std::format("{}", v); }

std::string format_motion(const char* code, const MotionWords& words, int precision) {
    std::vector<std::string> parts{code};
    if (words.x) {
        parts.emplace_back("X" + format_fixed(*words.x, precision));
    }
    if (words.y) {
        parts.emplace_back("Y" + format_fixed(*words.y, precision));
    }
    if (words.z) {
        parts.emplace_back("Z" + format_fixed(*words.z, precision));
    }
    if (words.feed) {
        parts.emplace_back("F" + format_fixed(*words.feed, feed_precision(precision)));
    }
    std::ostringstream oss;
    for (std::size_t i = 0; i < parts.size(); ++i) {
        if (i > 0) {
            oss << ' ';
        }
        oss << parts[i];
    }
    return oss.str();
}

}  // namespace millui::native::algo
