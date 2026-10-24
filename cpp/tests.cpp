#include "sensor_stream.hpp"

#include <cmath>
#include <future>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

using namespace std::chrono_literals;

namespace {
void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

void queue_capacity_and_drain() {
    bool rejected = false;
    try { sensor::BoundedQueue invalid(0); }
    catch (const std::invalid_argument&) { rejected = true; }
    require(rejected, "zero capacity must fail");

    sensor::BoundedQueue queue(2);
    require(queue.push(sensor::make_frame(10)), "first push");
    require(queue.push(sensor::make_frame(11)), "second push");
    require(!queue.push(sensor::make_frame(12), sensor::OverflowPolicy::drop_newest),
            "full queue must drop newest");
    auto counts = queue.counters();
    require(counts.queued == 2 && counts.high_watermark == 2 && counts.dropped == 1,
            "capacity and drop counters");
    queue.close();
    queue.close();
    require(!queue.push(sensor::make_frame(13)), "closed queue rejects writes");
    const auto first = queue.pop();
    const auto second = queue.pop();
    require(first && second && first->sequence == 10 && second->sequence == 11,
            "close must preserve FIFO and drain accepted frames");
    require(!queue.pop(), "drained closed queue must end stream");
    counts = queue.counters();
    require(counts.enqueued == 2 && counts.consumed == 2 && counts.queued == 0 &&
            counts.dropped == 1, "closed writes are not overflow drops");
}

void close_wakes_waiters() {
    sensor::BoundedQueue full(1);
    full.push(sensor::make_frame(0));
    auto writer = std::async(std::launch::async, [&] {
        return full.push(sensor::make_frame(1));
    });
    const bool writer_waited = writer.wait_for(30ms) == std::future_status::timeout;
    full.close();
    require(writer.wait_for(1s) == std::future_status::ready, "close wakes writer");
    require(!writer.get() && writer_waited, "full writer waits then rejects on close");

    sensor::BoundedQueue empty(1);
    auto reader = std::async(std::launch::async, [&] { return empty.pop(); });
    const bool reader_waited = reader.wait_for(30ms) == std::future_status::timeout;
    empty.close();
    require(reader.wait_for(1s) == std::future_status::ready, "close wakes reader");
    require(!reader.get() && reader_waited, "empty reader waits then ends on close");
}

void concurrent_fifo_and_wraparound() {
    sensor::BoundedQueue queue(3);
    constexpr std::uint64_t total = 10000;
    auto reader = std::async(std::launch::async, [&] {
        std::uint64_t expected = 0;
        bool ordered = true;
        while (auto frame = queue.pop()) {
            ordered = ordered && frame->sequence == expected;
            ++expected;
        }
        return ordered && expected == total;
    });
    for (std::uint64_t i = 0; i < total; ++i) queue.push(sensor::make_frame(i));
    queue.close();
    require(reader.get(), "concurrent FIFO order over repeated ring wraparound");
    const auto counts = queue.counters();
    require(counts.enqueued == total && counts.consumed == total &&
            counts.dropped == 0 && counts.queued == 0 && counts.high_watermark <= 3,
            "blocking stream must preserve all frames within capacity");
}

void frames_and_simulator_accounting() {
    const auto zero = sensor::make_frame(0);
    const auto next = sensor::make_frame(1000);
    require(zero.sequence == 0 && zero.elapsed_seconds == 0 &&
            zero.temperature_c == 25 && zero.pressure_kpa == 205,
            "known initial synthetic frame");
    require(next.sequence == 1000 && next.elapsed_seconds == 1 &&
            std::abs(next.temperature_c - (25 + 2 * std::sin(1.0))) < 1e-12,
            "sequence determines sample time and values");
    sensor::Config config;
    config.frames = 2000;
    config.capacity = 1;
    auto result = sensor::run(config);
    require(result.produced == 2000 && result.counters.consumed == 2000 &&
            result.counters.enqueued == 2000 && result.counters.dropped == 0 &&
            result.last_frame && result.last_frame->sequence == 1999,
            "lossless run accounting and final frame");
    config.policy = sensor::OverflowPolicy::drop_newest;
    config.consumer_delay = 50us;
    result = sensor::run(config);
    require(result.produced == result.counters.enqueued + result.counters.dropped &&
            result.counters.enqueued == result.counters.consumed &&
            result.counters.queued == 0 && result.counters.high_watermark <= 1,
            "drop mode conserves frames and drains on shutdown");
    // Overflow itself is tested deterministically in queue_capacity_and_drain;
    // thread scheduling does not determine whether this test passes.
    config.frames = 0;
    result = sensor::run(config);
    require(result.produced == 0 && result.counters.consumed == 0 &&
            !result.last_frame, "empty run shuts down cleanly");
    config.producer_delay = -1us;
    bool rejected = false;
    try { sensor::run(config); }
    catch (const std::invalid_argument&) { rejected = true; }
    require(rejected, "negative delays rejected");
}
}

int main() {
    try {
        queue_capacity_and_drain();
        close_wakes_waiters();
        concurrent_fifo_and_wraparound();
        frames_and_simulator_accounting();
        std::cout << "All sensor stream tests passed\n";
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
