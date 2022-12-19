import contextlib
import time


class MeterBase(object):
    @contextlib.contextmanager
    def record_duration(self, name: str, **kargs):
        start_at = time.time()
        yield
        duration = time.time() - start_at
        histogram = self._get_histogram(name)
        if histogram:
            histogram.record(duration, **kargs)

    def count(self, name: str, count: int = 1, **kargs):
        counter = self._get_counter(name)
        if counter:
            counter.add(count)

    def _get_histogram(self, name: str):
        return None

    def _get_counter(self, name: str):
        return None


class OpenTelemetryMeter(MeterBase):
    def __init__(self, meter):
        self._meter = meter
        self._histograms = {}
        self._counters = {}
        self._add_historgram(
            name="build_directory_seconds",
            description="measures the duration of building directory",
            unit="seconds",
        )
        self._add_counter(
            name="evict_cached_directory",
            description="measures the count of evicted directory",
        )
        self._add_counter(
            name="evict_cached_file",
            description="measures the count of evicted files",
        )

    def _add_historgram(
        self,
        name: str,
        description: str = "",
        unit: str = "seconds",
    ):
        h = self._meter.create_histogram(
            name=name,
            description=description,
            unit=unit,
        )
        self._histograms[name] = h
        return h

    def _add_counter(
        self,
        name: str,
        description: str = "",
    ):
        c = self._meter.create_counter(
            name=name,
            description=description,
        )
        self._counters[name] = c
        return c

    def _get_histogram(self, name: str):
        try:
            result = self._histograms[name]
        except KeyError:
            result = self._add_historgram(name)
        return result

    def _get_counter(self, name: str):
        try:
            result = self._counters[name]
        except KeyError:
            result = self._add_counter(name)
        return result


def create_meter():
    from opentelemetry import metrics
    from opentelemetry.exporter.prometheus import PrometheusMetricReader
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource

    resource = Resource(attributes={SERVICE_NAME: "buildbarn"})
    reader = PrometheusMetricReader(prefix="buildbarn")
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    return OpenTelemetryMeter(metrics.get_meter("buildbarn"))


def create_dummy_meter():
    return MeterBase()
