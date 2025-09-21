#pragma once

#include "millui/native/facade.hpp"

namespace millui::native::algo {

std::string post_gcode(const Paths& paths, const PostConfig& cfg);

}  // namespace millui::native::algo
