from fastapi import FastAPI

from app.src.routes import data, health, orders, users

app = FastAPI(
    title="DevOps Digital Twin Demo Application",
    description="Phase 2 cloud-native demo workload for the DevOps Digital Twin project.",
    version="1.0.0",
)

app.include_router(health.router)
app.include_router(users.router)
app.include_router(data.router)
app.include_router(orders.router)
