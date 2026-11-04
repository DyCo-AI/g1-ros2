#include "g1_teleop/dex3_motion.hpp"

#include <unitree/idl/hg/HandCmd_.hpp>
#include <unitree/idl/hg/HandState_.hpp>
#include <unitree/robot/channel/channel_publisher.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>

#include <chrono>
#include <csignal>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <poll.h>
#include <stdexcept>
#include <string>
#include <thread>
#include <unistd.h>

namespace dex3 = g1_teleop::dex3;
using Clock = std::chrono::steady_clock;
using Command = unitree_hg::msg::dds_::HandCmd_;
using State = unitree_hg::msg::dds_::HandState_;

namespace {

volatile std::sig_atomic_t interrupted = 0;

void interrupt_handler(int) { interrupted = 1; }

double seconds(Clock::time_point time) {
  return std::chrono::duration<double>(time.time_since_epoch()).count();
}

struct Options {
  std::string interface;
  dex3::Side side = dex3::Side::kRight;
  bool enable_motion = false;
};

void print_usage(const char* program) {
  std::cout
      << "Usage: " << program
      << " NETWORK_INTERFACE [--side left|right] [--enable-motion]\n\n"
      << "Without --enable-motion this performs a read-only feedback check and "
         "never creates a command publisher.\n";
}

Options parse_options(int argc, char** argv) {
  Options options;
  for (int index = 1; index < argc; ++index) {
    const std::string argument = argv[index];
    if (argument == "--help" || argument == "-h") {
      print_usage(argv[0]);
      std::exit(0);
    }
    if (argument == "--enable-motion") {
      options.enable_motion = true;
      continue;
    }
    if (argument == "--side") {
      if (++index >= argc) throw std::invalid_argument("--side requires a value");
      options.side = dex3::parse_side(argv[index]);
      continue;
    }
    if (!argument.empty() && argument.front() == '-') {
      throw std::invalid_argument("Unknown option: " + argument);
    }
    if (!options.interface.empty()) {
      throw std::invalid_argument("Only one network interface may be supplied");
    }
    options.interface = argument;
  }
  if (options.interface.empty()) {
    throw std::invalid_argument("NETWORK_INTERFACE is required");
  }
  return options;
}

struct Feedback {
  dex3::JointArray position{};
  Clock::time_point received{};
  unsigned long count = 0;
  std::string fault;
};

Command make_command(const dex3::JointArray& position, bool release = false) {
  Command message;
  message.motor_cmd().resize(7);
  for (std::size_t index = 0; index < message.motor_cmd().size(); ++index) {
    auto& motor = message.motor_cmd()[index];
    motor.mode(static_cast<uint8_t>(index) | 0x10U | (release ? 0x80U : 0x00U));
    motor.q(release ? 0.0 : position[index]);
    motor.dq(0.0);
    motor.tau(0.0);
    motor.kp(release ? 0.0 : 1.5);
    motor.kd(release ? 0.0 : 0.2);
  }
  return message;
}

}  // namespace

int main(int argc, char** argv) {
  Options options;
  try {
    options = parse_options(argc, argv);
  } catch (const std::exception& error) {
    std::cerr << "Argument error: " << error.what() << "\n\n";
    print_usage(argv[0]);
    return 1;
  }

  std::signal(SIGINT, interrupt_handler);
  std::signal(SIGTERM, interrupt_handler);
  std::signal(SIGHUP, interrupt_handler);

  const std::string side = dex3::side_name(options.side);
  const std::string state_topic = "rt/lf/dex3/" + side + "/state";
  const std::string command_topic = "rt/dex3/" + side + "/cmd";

  std::mutex mutex;
  Feedback feedback;
  Clock::time_point last_foreign_command{};
  bool monitor_foreign_commands = true;
  bool command_attempted = false;
  int result = 0;
  std::ofstream log;
  unitree::robot::ChannelSubscriberPtr<State> state_subscriber;
  unitree::robot::ChannelSubscriberPtr<Command> command_monitor;
  unitree::robot::ChannelPublisherPtr<Command> publisher;

  try {
    unitree::robot::ChannelFactory::Instance()->Init(0, options.interface);
    state_subscriber =
        std::make_shared<unitree::robot::ChannelSubscriber<State>>(state_topic);
    state_subscriber->InitChannel(
        [&](const void* raw) {
          const auto& message = *static_cast<const State*>(raw);
          const auto now = Clock::now();
          std::lock_guard<std::mutex> guard(mutex);
          if (message.motor_state().size() != 7) {
            feedback.fault = "Expected seven hand motors";
            return;
          }
          for (const auto error : message.error()) {
            if (error != 0) feedback.fault = "Hand reports an error word";
          }
          dex3::JointArray position{};
          for (std::size_t index = 0; index < position.size(); ++index) {
            position[index] = message.motor_state()[index].q();
          }
          const double interval = seconds(now) - seconds(feedback.received);
          if (feedback.count > 0 && interval >= 0.02 && interval <= 0.5) {
            for (std::size_t index = 0; index < position.size(); ++index) {
              if (std::abs(position[index] - feedback.position[index]) / interval > 0.5) {
                feedback.fault =
                    "Position-derived speed exceeds 0.5 rad/s on motor " +
                    std::to_string(index);
              }
            }
          }
          feedback.position = position;
          feedback.received = now;
          ++feedback.count;
        },
        1);

    command_monitor =
        std::make_shared<unitree::robot::ChannelSubscriber<Command>>(command_topic);
    command_monitor->InitChannel(
        [&](const void*) {
          std::lock_guard<std::mutex> guard(mutex);
          if (monitor_foreign_commands) last_foreign_command = Clock::now();
        },
        1);

    const auto read_feedback = [&]() {
      std::lock_guard<std::mutex> guard(mutex);
      return feedback;
    };
    const auto validate = [&](const Feedback& current) {
      if (current.count < 3 ||
          seconds(Clock::now()) - seconds(current.received) > 0.5) {
        throw std::runtime_error("Hand feedback missing or stale (>0.5 s)");
      }
      if (!current.fault.empty()) throw std::runtime_error(current.fault);
      dex3::bounded(current.position, options.side);
    };
    const auto print_feedback = [&](const Feedback& current) {
      std::cout << side << " measured q (degrees):";
      for (const double position : current.position) {
        std::cout << ' ' << std::fixed << std::setprecision(2)
                  << position * 180.0 / dex3::kPi;
      }
      std::cout << " | packets " << current.count << '\n' << std::flush;
    };

    std::cout << "READ-ONLY: waiting for " << side
              << " Dex3 feedback on " << state_topic
              << "; no motor commands.\n" << std::flush;
    const auto ready_at = Clock::now() + std::chrono::seconds(3);
    while (Clock::now() < ready_at && !interrupted) {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    if (interrupted) throw std::runtime_error("Interrupted before activation");
    validate(read_feedback());
    print_feedback(read_feedback());

    if (!options.enable_motion) {
      std::cout << "PASS: read-only feedback check completed; no command publisher "
                   "was created.\n";
    } else {
      std::cout
          << "MOTION ENABLED BUT DISENGAGED. Robot must be supported; keep the "
             "hand empty and its sweep clear.\n"
          << "o=open 10 deg; c=close 10 deg; r=return captured start; "
             "p=print; s/q=release and exit.\n"
          << "Type one key and Enter. Each move takes six seconds and remains "
             "within 30 degrees of the captured start.\n"
          << "Motor 0 remains at its captured angle. Ctrl+C, EOF, a handled "
             "fault, or 60 seconds idle attempts zero-effort release.\n"
          << std::flush;
    }

    dex3::JointArray home{};
    dex3::JointArray start{};
    dex3::JointArray target{};
    dex3::JointArray desired{};
    bool active = false;
    bool moving = false;
    auto movement_start = Clock::now();
    auto last_input = movement_start;
    auto last_tick = movement_start;
    auto last_log = movement_start;
    Clock::time_point settled_since{};
    std::string input;

    while (options.enable_motion && !interrupted) {
      const auto now = Clock::now();
      const double loop_interval = seconds(now) - seconds(last_tick);
      last_tick = now;
      auto current = read_feedback();
      validate(current);
      if (active && loop_interval > 0.15) {
        throw std::runtime_error("Control loop gap exceeds 0.15 s");
      }
      if (seconds(now) - seconds(last_input) > 60.0) {
        throw std::runtime_error("60 s operator idle timeout");
      }

      pollfd descriptor{STDIN_FILENO, POLLIN, 0};
      const int available = poll(&descriptor, 1, 0);
      char action = 0;
      if (available < 0 && !interrupted) {
        throw std::runtime_error("stdin poll failed");
      }
      if (available > 0 &&
          (descriptor.revents & (POLLIN | POLLHUP | POLLERR)) != 0) {
        char character = 0;
        if (::read(STDIN_FILENO, &character, 1) <= 0) break;
        if (character == '\n') {
          if (input.size() == 1) {
            action = input.front();
          } else if (!input.empty()) {
            std::cout << "Enter one command: o/c/r/p/s/q\n";
          }
          input.clear();
        } else if (input.size() < 32) {
          input += character;
        }
      }

      if (action != 0) last_input = now;
      if (action == 'q' || action == 's') break;
      if (action == 'p') print_feedback(current);
      if (action == 'o' || action == 'c' || action == 'r') {
        if (moving) {
          std::cout << "Wait for SETTLED before another move; s releases now.\n";
        } else if (!active && action == 'r') {
          std::cout << "No captured start exists; use o or c first.\n";
        } else {
          if (!active) {
            {
              std::lock_guard<std::mutex> guard(mutex);
              if (last_foreign_command != Clock::time_point{}) {
                throw std::runtime_error(
                    "Another hand command stream was observed; stop it first");
              }
            }
            publisher =
                std::make_shared<unitree::robot::ChannelPublisher<Command>>(
                    command_topic);
            publisher->InitChannel();
            const auto discovery_end = Clock::now() + std::chrono::seconds(3);
            while (Clock::now() < discovery_end && !interrupted) {
              validate(read_feedback());
              std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
            if (interrupted) break;
            {
              std::lock_guard<std::mutex> guard(mutex);
              if (last_foreign_command != Clock::time_point{}) {
                throw std::runtime_error(
                    "Another hand command stream was observed during discovery");
              }
              monitor_foreign_commands = false;
            }
            current = read_feedback();
            validate(current);
            home = desired = dex3::bounded(current.position, options.side);
            const auto stamp = std::chrono::duration_cast<std::chrono::nanoseconds>(
                                   Clock::now().time_since_epoch())
                                   .count();
            const std::string filename =
                "dex3_" + side + "_session_" + std::to_string(stamp) + ".csv";
            log.open(filename);
            if (!log) throw std::runtime_error("Cannot create diagnostic CSV");
            log << "steady_seconds,moving,motor,command_rad,measured_rad,"
                   "feedback_age_seconds\n";
            std::cout << "Session log: " << filename << '\n';
            active = true;
            last_tick = Clock::now();
          }

          start = desired;
          target = action == 'r'
                       ? home
                       : dex3::step_target(
                             start, home, options.side, action == 'c');
          movement_start = Clock::now();
          settled_since = Clock::time_point{};
          moving = true;
          std::cout << "MOVING " << action << "; target degrees:";
          for (const double position : target) {
            std::cout << ' ' << position * 180.0 / dex3::kPi;
          }
          std::cout << '\n' << std::flush;
        }
      }

      if (active) {
        const auto at = Clock::now();
        current = read_feedback();
        validate(current);
        const double elapsed = seconds(at) - seconds(movement_start);
        desired = dex3::interpolate(start, target, elapsed);
        for (std::size_t index = 0; index < desired.size(); ++index) {
          if (std::abs(current.position[index] - desired[index]) >
              dex3::kTrackingLimit) {
            throw std::runtime_error(
                "Motor " + std::to_string(index) +
                " tracking error exceeds 0.15 rad");
          }
        }
        command_attempted = true;
        if (!publisher->Write(make_command(desired))) {
          throw std::runtime_error("DDS command write failed");
        }
        if (seconds(at) - seconds(last_log) >= 0.1) {
          for (std::size_t index = 0; index < desired.size(); ++index) {
            log << std::setprecision(12) << seconds(at) << ',' << moving << ','
                << index << ',' << desired[index] << ','
                << current.position[index] << ','
                << seconds(at) - seconds(current.received) << '\n';
          }
          log.flush();
          if (!log) throw std::runtime_error("Diagnostic log write failed");
          last_log = at;
        }
        if (moving && elapsed >= dex3::kMoveDuration) {
          if (dex3::maximum_error(current.position, target) <= 0.06) {
            if (settled_since == Clock::time_point{}) settled_since = at;
            if (seconds(at) - seconds(settled_since) >= 0.4) {
              moving = false;
              std::cout << "SETTLED; holding. o/c/r for another move, "
                           "s/q to release.\n";
              print_feedback(current);
            }
          } else {
            settled_since = Clock::time_point{};
          }
          if (moving && elapsed > dex3::kMoveDuration + 5.0) {
            throw std::runtime_error(
                "Target not reached within the settling timeout");
          }
        }
      }

      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
  } catch (const std::exception& error) {
    std::cerr << "STOPPED: " << error.what() << '\n';
    result = 2;
  }

  if (command_attempted && publisher) {
    bool release_ok = true;
    for (int attempt = 0; attempt < 5; ++attempt) {
      try {
        if (!publisher->Write(make_command(dex3::JointArray{}, true))) {
          release_ok = false;
        }
      } catch (...) {
        release_ok = false;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    std::cout << (release_ok ? "Zero-effort release commands sent.\n"
                             : "Release delivery is uncertain.\n");
  }
  if (publisher) publisher->CloseChannel();
  if (command_monitor) command_monitor->CloseChannel();
  if (state_subscriber) state_subscriber->CloseChannel();
  return result;
}
