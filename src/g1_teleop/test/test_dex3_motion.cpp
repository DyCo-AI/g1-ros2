#include "g1_teleop/dex3_motion.hpp"

#include <gtest/gtest.h>

namespace dex3 = g1_teleop::dex3;

TEST(Dex3Motion, ParsesSides) {
  EXPECT_EQ(dex3::parse_side("left"), dex3::Side::kLeft);
  EXPECT_EQ(dex3::parse_side("right"), dex3::Side::kRight);
  EXPECT_THROW(dex3::parse_side("both"), std::invalid_argument);
}

TEST(Dex3Motion, RightCloseUsesExpectedFlexionSigns) {
  dex3::JointArray home{};
  const auto target = dex3::step_target(home, home, dex3::Side::kRight, true);
  EXPECT_DOUBLE_EQ(target[0], 0.0);
  EXPECT_LT(target[1], 0.0);
  EXPECT_LT(target[2], 0.0);
  for (std::size_t index = 3; index < target.size(); ++index) {
    EXPECT_GT(target[index], 0.0);
  }
}

TEST(Dex3Motion, LeftCloseMirrorsRightClose) {
  dex3::JointArray home{};
  const auto target = dex3::step_target(home, home, dex3::Side::kLeft, true);
  EXPECT_DOUBLE_EQ(target[0], 0.0);
  EXPECT_GT(target[1], 0.0);
  EXPECT_GT(target[2], 0.0);
  for (std::size_t index = 3; index < target.size(); ++index) {
    EXPECT_LT(target[index], 0.0);
  }
}

TEST(Dex3Motion, OpenReversesClose) {
  dex3::JointArray home{};
  const auto closed = dex3::step_target(home, home, dex3::Side::kRight, true);
  const auto reopened = dex3::step_target(closed, home, dex3::Side::kRight, false);
  for (std::size_t index = 0; index < home.size(); ++index) {
    EXPECT_NEAR(reopened[index], home[index], 1e-12);
  }
}

TEST(Dex3Motion, SessionEnvelopeLimitsRepeatedSteps) {
  dex3::JointArray home{};
  auto target = home;
  for (int count = 0; count < 20; ++count) {
    target = dex3::step_target(target, home, dex3::Side::kRight, true);
  }
  for (std::size_t index = 1; index < target.size(); ++index) {
    EXPECT_LE(std::abs(target[index] - home[index]),
              dex3::kSessionEnvelope + 1e-12);
  }
}

TEST(Dex3Motion, SmoothInterpolationHasFixedEndpoints) {
  dex3::JointArray start{};
  dex3::JointArray end{};
  end.fill(0.5);
  EXPECT_EQ(dex3::interpolate(start, end, 0.0), start);
  EXPECT_EQ(dex3::interpolate(start, end, dex3::kMoveDuration), end);
  const auto midpoint = dex3::interpolate(start, end, dex3::kMoveDuration / 2.0);
  EXPECT_NEAR(midpoint[3], 0.25, 1e-12);
}

TEST(Dex3Motion, RejectsFeedbackOutsideMargin) {
  dex3::JointArray feedback{};
  feedback[3] = dex3::kRightUpper[3] + 0.061;
  EXPECT_THROW(dex3::bounded(feedback, dex3::Side::kRight), std::runtime_error);
}
