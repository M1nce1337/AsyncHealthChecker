from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import main_router
from database.db_helper import db_helper
import uvicorn



@asynccontextmanager
async def lifespan(app: FastAPI):
    # При запуске приложения инициализируем ресурсы
    yield
    # При остановке приложения освобождаем ресурсы
    await db_helper.dispose()


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
        reload=True
)