#include "sensor_stream.hpp"

#include <charconv>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>

namespace {
std::uint64_t number(std::string_view text, std::uint64_t maximum) {
    std::uint64_t value{};
    const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
    if (error != std::errc{} || end != text.data() + text.size() || value > maximum) {
        throw std::invalid_argument("invalid numeric value: " + std::string(text));
    }
    return value;
}
}

int main(int argc, char** argv) {
    try {
        sensor::Config config;
        for (int i = 1; i < argc; ++i) {
            const std::string_view option = argv[i];
            if (option == "--help") {
                std::cout << "Usage: sensor_simulator [--frames N] [--capacity N] "
                             "[--producer-us N] [--consumer-us N] [--drop-on-full]\n";
                return 0;
            }
            if (option == "--drop-on-full") {
                config.policy = sensor::OverflowPolicy::drop_newest;
                continue;
            }
            if (option != "--frames" && option != "--capacity" &&
                option != "--producer-us" && option != "--consumer-us") {
                throw std::invalid_argument("unknown option: " + std::string(option));
            }
            if (++i == argc) {
                throw std::invalid_argument("missing value for " + std::string(option));
            }
            const std::string_view value = argv[i];
            if (option == "--frames") {
                config.frames = number(value, std::numeric_limits<std::uint64_t>::max());
            } else if (option == "--capacity") {
                config.capacity = static_cast<std::size_t>(
                    number(value, std::numeric_limits<std::size_t>::max()));
            } else {
                const auto delay = std::chrono::microseconds(number(value,
                    std::numeric_limits<std::chrono::microseconds::rep>::max()));
                if (option == "--producer-us") config.producer_delay = delay;
                else config.consumer_delay = delay;
            }
        }
        const auto result = sensor::run(config);
        const auto& counts = result.counters;
        std::cout << "produced=" << result.produced << " enqueued=" << counts.enqueued
                  << " consumed=" << counts.consumed << " dropped=" << counts.dropped
                  << " queued=" << counts.queued
                  << " high_watermark=" << counts.high_watermark << '\n';
        if (result.last_frame) {
            const auto& frame = *result.last_frame;
            std::cout << "last_frame: sequence=" << frame.sequence
                      << " elapsed_seconds=" << frame.elapsed_seconds
                      << " temperature_c=" << frame.temperature_c
                      << " pressure_kpa=" << frame.pressure_kpa
                      << " flow_kg_s=" << frame.flow_kg_s << '\n';
        }
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
