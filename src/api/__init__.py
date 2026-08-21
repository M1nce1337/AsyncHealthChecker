from fastapi import APIRouter

from api.v1 import main_router as v1_router

main_router = APIRouter(prefix="/api")

main_router.include_router(v1_router)
