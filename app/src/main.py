from time import perf_counter

from fastapi import FastAPI
from prometheus_client import Counter, Histogram

from app.src.routes import data, experiments, health, orders, users


HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests handled by the application.",
    ("method", "path", "status"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "path"),
)

app = FastAPI(
    title="DevOps Digital Twin Demo Application",
    description="Phase 2 cloud-native demo workload for the DevOps Digital Twin project.",
    version="1.0.0",
)


@app.middleware("http")
async def collect_http_metrics(request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)

    start_time = perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    except Exception:
        HTTP_REQUESTS_TOTAL.labels(request.method, request.url.path, "500").inc()
        raise
    finally:
        HTTP_REQUEST_DURATION_SECONDS.labels(
            request.method, request.url.path
        ).observe(perf_counter() - start_time)
        if response is not None:
            HTTP_REQUESTS_TOTAL.labels(
                request.method, request.url.path, str(response.status_code)
            ).inc()

app.include_router(health.router)
app.include_router(users.router)
app.include_router(data.router)
app.include_router(orders.router)
app.include_router(experiments.router)
