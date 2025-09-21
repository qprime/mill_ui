#pragma once

#include <string>

namespace millui::native {

enum class StatusCode {
  Ok = 0,
  InvalidArgument,
  IOError,
  NotImplemented,
  Internal,
};

struct Status {
  StatusCode code = StatusCode::Ok;
  std::string message;

  constexpr Status() = default;
  constexpr Status(StatusCode c, std::string msg)
      : code(c), message(std::move(msg)) {}

  [[nodiscard]] constexpr bool ok() const noexcept { return code == StatusCode::Ok; }
};

inline Status status_ok() { return {}; }
inline Status status_invalid(std::string msg) { return {StatusCode::InvalidArgument, std::move(msg)}; }
inline Status status_io(std::string msg) { return {StatusCode::IOError, std::move(msg)}; }
inline Status status_not_impl(std::string msg) { return {StatusCode::NotImplemented, std::move(msg)}; }
inline Status status_internal(std::string msg) { return {StatusCode::Internal, std::move(msg)}; }

}  // namespace millui::native
