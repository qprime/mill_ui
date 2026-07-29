#pragma once

#include <algorithm>
#include <optional>
#include <string>

namespace millui::native::algo {

[[nodiscard]] std::string format_fixed(double v, int precision);

[[nodiscard]] std::string format_compact(double v);

[[nodiscard]] constexpr int feed_precision(int precision) { return std::max(0, precision - 2); }

struct MotionWords {
    std::optional<double> x = std::nullopt;
    std::optional<double> y = std::nullopt;
    std::optional<double> z = std::nullopt;
    std::optional<double> feed = std::nullopt;
};

[[nodiscard]] std::string format_motion(const char* code, const MotionWords& words, int precision);

}  // namespace millui::native::algo
