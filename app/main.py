"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, products, requests


app = FastAPI(
    title="RMB Restock",
    description="Procurement request system for retail",
    version="0.1.0",
)

# Allow the React frontend to call us during dev. Tighten in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(requests.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
