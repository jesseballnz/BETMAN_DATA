from __future__ import annotations

from collections import defaultdict

_BUCKETS = (50, 100, 250, 500, 1_000, 2_500, 5_000)


class MetricsCollector:
    def __init__(self) -> None:
        self.request_totals: defaultdict[tuple[str, str, str], int] = defaultdict(int)
        self.latency_buckets: defaultdict[tuple[str, str, str, str], int] = defaultdict(int)
        self.latency_sums: defaultdict[tuple[str, str], float] = defaultdict(float)

    def observe(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        status = str(status_code)
        labels = (method, path, status)
        self.request_totals[labels] += 1
        self.latency_sums[(method, path)] += duration_ms / 1000

        for bucket in _BUCKETS:
            if duration_ms <= bucket:
                self.latency_buckets[(method, path, status, str(bucket / 1000))] += 1
        self.latency_buckets[(method, path, status, "+Inf")] += 1

    def render(self) -> str:
        lines = [
            "# HELP betman_api_requests_total Total HTTP requests handled by BETMAN API.",
            "# TYPE betman_api_requests_total counter",
        ]
        for (method, path, status), value in sorted(self.request_totals.items()):
            lines.append(
                "betman_api_requests_total"
                f'{{method="{method}",path="{path}",status="{status}"}} {value}'
            )

        lines.extend(
            [
                "# HELP betman_api_request_duration_seconds Request duration histogram.",
                "# TYPE betman_api_request_duration_seconds histogram",
            ]
        )
        for (method, path, status, bucket), value in sorted(self.latency_buckets.items()):
            lines.append(
                "betman_api_request_duration_seconds_bucket"
                f'{{method="{method}",path="{path}",status="{status}",le="{bucket}"}} {value}'
            )
        for (method, path), value in sorted(self.latency_sums.items()):
            lines.append(
                "betman_api_request_duration_seconds_sum"
                f'{{method="{method}",path="{path}"}} {value:.6f}'
            )
        return "\n".join(lines) + "\n"


metrics = MetricsCollector()
