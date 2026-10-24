#pragma once

#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <optional>
#include <vector>

namespace sensor {

struct Frame {
    std::uint64_t sequence{};
    double elapsed_seconds{};
    double temperature_c{};
    double pressure_kpa{};
    double flow_kg_s{};
};

enum class OverflowPolicy { block, drop_newest };

struct Counters {
    std::uint64_t enqueued{};
    std::uint64_t consumed{};
    std::uint64_t dropped{};
    std::size_t queued{};
    std::size_t high_watermark{};
};

// Fixed storage; all state and counters are protected by the same mutex.
// close() rejects writes, wakes waiters, and allows readers to drain the queue.
// All worker threads must finish before destroying the queue.
class BoundedQueue {
public:
    explicit BoundedQueue(std::size_t capacity);
    bool push(Frame frame, OverflowPolicy policy = OverflowPolicy::block);
    std::optional<Frame> pop();
    void close();
    Counters counters() const;

private:
    std::vector<Frame> storage_;
    mutable std::mutex mutex_;
    std::condition_variable readable_;
    std::condition_variable writable_;
    std::size_t head_{};
    bool closed_{};
    Counters counters_;
};

struct Config {
    std::uint64_t frames{1000};
    std::size_t capacity{16};
    // Zero runs as fast as possible. Sample timestamps always advance by 1 ms.
    std::chrono::microseconds producer_delay{0};
    std::chrono::microseconds consumer_delay{0};
    OverflowPolicy policy{OverflowPolicy::block};
};

struct Result {
    std::uint64_t produced{};
    Counters counters;
    std::optional<Frame> last_frame;
};

Frame make_frame(std::uint64_t sequence);
Result run(const Config& config);

}  // namespace sensor
