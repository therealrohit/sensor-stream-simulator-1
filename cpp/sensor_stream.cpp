#include "sensor_stream.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <thread>

namespace sensor {

BoundedQueue::BoundedQueue(std::size_t capacity) {
    if (capacity == 0) {
        throw std::invalid_argument("capacity must be greater than zero");
    }
    storage_.resize(capacity);
}

bool BoundedQueue::push(Frame frame, OverflowPolicy policy) {
    std::unique_lock lock(mutex_);
    if (policy == OverflowPolicy::block) {
        writable_.wait(lock, [this] {
            return closed_ || counters_.queued < storage_.size();
        });
    }
    if (closed_) {
        return false;
    }
    if (counters_.queued == storage_.size()) {
        ++counters_.dropped;
        return false;
    }
    storage_[(head_ + counters_.queued) % storage_.size()] = frame;
    ++counters_.queued;
    ++counters_.enqueued;
    counters_.high_watermark = std::max(counters_.high_watermark, counters_.queued);
    lock.unlock();
    readable_.notify_one();
    return true;
}

std::optional<Frame> BoundedQueue::pop() {
    std::unique_lock lock(mutex_);
    readable_.wait(lock, [this] { return closed_ || counters_.queued != 0; });
    if (counters_.queued == 0) {
        return std::nullopt;
    }
    auto frame = storage_[head_];
    head_ = (head_ + 1) % storage_.size();
    --counters_.queued;
    ++counters_.consumed;
    lock.unlock();
    writable_.notify_one();
    return frame;
}

void BoundedQueue::close() {
    {
        std::lock_guard lock(mutex_);
        closed_ = true;
    }
    readable_.notify_all();
    writable_.notify_all();
}

Counters BoundedQueue::counters() const {
    std::lock_guard lock(mutex_);
    return counters_;
}

Frame make_frame(std::uint64_t sequence) {
    const double t = static_cast<double>(sequence) * 0.001;
    return {sequence, t, 25.0 + 2.0 * std::sin(t),
            200.0 + 5.0 * std::cos(t), 0.39 + 0.02 * std::sin(t * 0.5)};
}

Result run(const Config& config) {
    if (config.producer_delay.count() < 0 || config.consumer_delay.count() < 0) {
        throw std::invalid_argument("delays must be nonnegative");
    }
    BoundedQueue queue(config.capacity);
    Result result;
    std::jthread consumer([&] {
        while (auto frame = queue.pop()) {
            result.last_frame = *frame;
            if (config.consumer_delay.count() != 0) {
                std::this_thread::sleep_for(config.consumer_delay);
            }
        }
    });
    // The producer runs on the caller thread; the consumer runs concurrently.
    for (std::uint64_t i = 0; i < config.frames; ++i) {
        ++result.produced;
        queue.push(make_frame(i), config.policy);
        if (config.producer_delay.count() != 0) {
            std::this_thread::sleep_for(config.producer_delay);
        }
    }
    queue.close();
    consumer.join();
    result.counters = queue.counters();
    return result;
}

}  // namespace sensor
