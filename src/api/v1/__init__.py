from fastapi import APIRouter

from api.v1.create_task import router as create_task_router
from api.v1.get_task import router as get_task_router

main_router = APIRouter(prefix="/v1", tags=["Tasks"])

main_router.include_router(create_task_router)
main_router.include_router(get_task_router)
