from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import income_verifications
from app.config import get_settings


settings = get_settings()

app = FastAPI(title="Income Verification Expert API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_v1_router = APIRouter()
api_v1_router.include_router(income_verifications.router)
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

