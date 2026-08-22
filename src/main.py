from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import main_router
from broker.redis_helper import redis_helper
from config import settings
from database.db_helper import db_helper
from logging_setup.logging_config import setup_logging
import structlog
import uvicorn

setup_logging()
log = structlog.get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # При запуске приложения инициализируем ресурсы
    await redis_helper.ping()
    log.info("api started", stream=settings.redis.stream)
    yield
    # При остановке приложения освобождаем ресурсы
    log.info("api stopping")
    await redis_helper.close()
    await db_helper.dispose()
    log.info("api stopped")


app = FastAPI(lifespan=lifespan)


app.include_router(main_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        reload=True,
        log_config=None,
)
