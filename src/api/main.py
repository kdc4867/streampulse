import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import dashboard

app = FastAPI(title="StreamPulse API")

cors_origins = os.getenv("CORS_ORIGINS", "")
allow_origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
if not allow_origins:
    allow_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.include_router(dashboard.router, prefix="/api")
