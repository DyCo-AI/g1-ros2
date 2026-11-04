#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>

namespace g1_teleop::dex3 {

using JointArray = std::array<double, 7>;

enum class Side { kLeft, kRight };

constexpr double kPi = 3.14159265358979323846;
constexpr double kStep = 10.0 * kPi / 180.0;
constexpr double kSessionEnvelope = 30.0 * kPi / 180.0;
constexpr double kMoveDuration = 6.0;
constexpr double kTrackingLimit = 0.15;

constexpr JointArray kLeftLower{-1.05, -0.724, 0.0, -1.57, -1.75, -1.57, -1.75};
constexpr JointArray kLeftUpper{1.05, 1.05, 1.75, 0.0, 0.0, 0.0, 0.0};
constexpr JointArray kRightLower{-1.05, -1.05, -1.75, 0.0, 0.0, 0.0, 0.0};
constexpr JointArray kRightUpper{1.05, 0.742, 0.0, 1.57, 1.75, 1.57, 1.75};

inline const JointArray& lower_limits(Side side) {
  return side == Side::kLeft ? kLeftLower : kRightLower;
}

inline const JointArray& upper_limits(Side side) {
  return side == Side::kLeft ? kLeftUpper : kRightUpper;
}

inline const char* side_name(Side side) {
  return side == Side::kLeft ? "left" : "right";
}

inline Side parse_side(const std::string& value) {
  if (value == "left") return Side::kLeft;
  if (value == "right") return Side::kRight;
  throw std::invalid_argument("--side must be left or right");
}

inline JointArray bounded(JointArray positions, Side side) {
  const auto& lower = lower_limits(side);
  const auto& upper = upper_limits(side);
  for (std::size_t index = 0; index < positions.size(); ++index) {
    if (!std::isfinite(positions[index]) ||
        positions[index] < lower[index] - 0.06 ||
        positions[index] > upper[index] + 0.06) {
      throw std::runtime_error(
          "Invalid or out-of-range feedback on motor " + std::to_string(index));
    }
    positions[index] = std::clamp(positions[index], lower[index], upper[index]);
  }
  return positions;
}

// Motor 0 is thumb opposition and remains at the captured starting angle.
// Flexion signs are mirrored between the left and right hands.
inline JointArray step_target(
    const JointArray& from, const JointArray& home, Side side, bool close) {
  JointArray target = from;
  target[0] = home[0];
  const auto& lower = lower_limits(side);
  const auto& upper = upper_limits(side);
  for (std::size_t index = 1; index < target.size(); ++index) {
    const double right_close_sign = index <= 2 ? -1.0 : 1.0;
    const double side_sign = side == Side::kRight ? 1.0 : -1.0;
    const double close_sign = right_close_sign * side_sign;
    const double direction = close ? close_sign : -close_sign;
    target[index] = std::clamp(
        from[index] + direction * kStep,
        std::max(lower[index], home[index] - kSessionEnvelope),
        std::min(upper[index], home[index] + kSessionEnvelope));
  }
  return target;
}

inline JointArray interpolate(
    const JointArray& start, const JointArray& end, double elapsed) {
  double fraction = std::clamp(elapsed / kMoveDuration, 0.0, 1.0);
  fraction = fraction * fraction * (3.0 - 2.0 * fraction);
  JointArray result{};
  for (std::size_t index = 0; index < result.size(); ++index) {
    result[index] = start[index] + fraction * (end[index] - start[index]);
  }
  return result;
}

inline double maximum_error(
    const JointArray& actual, const JointArray& desired) {
  double result = 0.0;
  for (std::size_t index = 0; index < actual.size(); ++index) {
    if (!std::isfinite(actual[index]) || !std::isfinite(desired[index])) {
      throw std::runtime_error("Nonfinite joint position");
    }
    result = std::max(result, std::abs(actual[index] - desired[index]));
  }
  return result;
}

}  // namespace g1_teleop::dex3
