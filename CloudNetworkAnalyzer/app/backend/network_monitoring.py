"""
Network Monitoring Module
Captures per-request metrics and maintains sliding window aggregates
"""

import time
import statistics
from collections import deque
from dataclasses import dataclass
from typing import List, Dict
import numpy as np


@dataclass
class NetworkMetrics:
    """Per-request network metrics"""
    timestamp: float
    session_id: str
    request_id: str
    latency_ms: float
    payload_size_bytes: int
    response_size_bytes: int
    http_status: int
    retry_count: int
    timeout_occurred: bool
    dns_resolution_ms: float = 0.0
    tls_handshake_ms: float = 0.0
    connection_establishment_ms: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "latency_ms": self.latency_ms,
            "payload_size_bytes": self.payload_size_bytes,
            "response_size_bytes": self.response_size_bytes,
            "http_status": self.http_status,
            "retry_count": self.retry_count,
            "timeout_occurred": self.timeout_occurred,
            "dns_resolution_ms": self.dns_resolution_ms,
            "tls_handshake_ms": self.tls_handshake_ms,
            "connection_establishment_ms": self.connection_establishment_ms,
        }


class SessionWindow:
    """Sliding window for session metrics"""

    def __init__(self, session_id: str, window_size: int = 10, window_seconds: int = 60):
        self.session_id = session_id
        self.window_size = window_size
        self.window_seconds = window_seconds
        self.requests: deque = deque(maxlen=window_size)
        self.last_success_time = time.time()

    def add_metric(self, metric: NetworkMetrics):
        """Add metric and enforce time window"""
        self.requests.append(metric)
        now = time.time()

        # remove requests outside time window
        while self.requests and (now - self.requests[0].timestamp > self.window_seconds):
            self.requests.popleft()

        if metric.http_status < 400:
            self.last_success_time = now

    def calculate_trend(self, values: List[float]) -> float:
        """Linear regression slope"""
        if len(values) < 2:
            return 0.0
        x = np.arange(len(values))
        slope, _ = np.polyfit(x, values, 1)
        return float(slope)

    def calculate_jitter(self, values: List[float]) -> float:
        """Mean absolute difference between consecutive latencies"""
        if len(values) < 2:
            return 0.0
        diffs = np.abs(np.diff(values))
        return float(np.mean(diffs))

    def aggregate_features(self) -> Dict:
        """Extract statistical features"""
        if not self.requests:
            return self._empty_features()

        latencies = [min(r.latency_ms, 2000) for r in self.requests]  # outlier protection
        payloads = [r.payload_size_bytes for r in self.requests]
        timestamps = [r.timestamp for r in self.requests]

        failures = sum(1 for r in self.requests if r.http_status >= 400)
        timeouts = sum(1 for r in self.requests if r.timeout_occurred)
        retries = sum(r.retry_count for r in self.requests)

        # request rate calculation
        duration = max(timestamps[-1] - timestamps[0], 1.0)
        velocity = len(self.requests) / duration

        # throughput
        total_bytes = sum(r.payload_size_bytes + r.response_size_bytes for r in self.requests)
        throughput = total_bytes / duration

        return {
            "avg_latency": statistics.mean(latencies),
            "std_latency": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
            "p95_latency": float(np.percentile(latencies, 95)),
            "p99_latency": float(np.percentile(latencies, 99)),
            "failure_rate": failures / len(self.requests),
            "timeout_rate": timeouts / len(self.requests),
            "avg_retries": retries / len(self.requests),
            "request_velocity": velocity,
            "latency_trend": self.calculate_trend(latencies),
            "jitter": self.calculate_jitter(latencies),
            "payload_trend": self.calculate_trend(payloads),
            "throughput_bytes_per_sec": throughput,
            "time_since_success": time.time() - self.last_success_time,
            "total_requests": len(self.requests),
        }

    def _empty_features(self) -> Dict:
        return {
            "avg_latency": 0.0,
            "std_latency": 0.0,
            "p95_latency": 0.0,
            "p99_latency": 0.0,
            "failure_rate": 0.0,
            "timeout_rate": 0.0,
            "avg_retries": 0.0,
            "request_velocity": 0.0,
            "latency_trend": 0.0,
            "jitter": 0.0,
            "payload_trend": 0.0,
            "throughput_bytes_per_sec": 0.0,
            "time_since_success": 0.0,
            "total_requests": 0,
        }


class NetworkMonitor:
    """Global monitoring service"""

    def __init__(self):
        self.session_windows: Dict[str, SessionWindow] = {}

    def get_or_create_window(self, session_id: str) -> SessionWindow:
        if session_id not in self.session_windows:
            self.session_windows[session_id] = SessionWindow(session_id)
        return self.session_windows[session_id]

    def record_request(self, metric: NetworkMetrics):
        window = self.get_or_create_window(metric.session_id)
        window.add_metric(metric)

    def get_session_features(self, session_id: str) -> Dict:
        window = self.get_or_create_window(session_id)
        return window.aggregate_features()

    def reset_session(self, session_id: str):
        if session_id in self.session_windows:
            del self.session_windows[session_id]

    def cleanup_sessions(self, max_idle_seconds: int = 300):
        """Remove inactive sessions"""
        now = time.time()
        for sid in list(self.session_windows.keys()):
            window = self.session_windows[sid]
            if now - window.last_success_time > max_idle_seconds:
                del self.session_windows[sid]


# Global monitor instance
network_monitor = NetworkMonitor()