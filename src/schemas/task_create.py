from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

MAX_URL_LENGTH = 2048
MAX_URLS_PER_TASK = 100


class TaskCreateRequest(BaseModel):
    """Тело запроса на создание задачи: список URL для проверки."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "urls": [
                        "https://ya.ru",
                        "https://google.com",
                        "https://github.com",
                    ]
                }
            ]
        }
    )

    urls: Annotated[
        list[HttpUrl],
        Field(
            min_length=1,
            max_length=MAX_URLS_PER_TASK,
            description="Непустой список http(s)-адресов для проверки доступности",
        ),
    ]

    @field_validator("urls", mode="after")
    @classmethod
    def validate_urls(cls, urls: list[HttpUrl]) -> list[HttpUrl]:
        for url in urls:
            if len(str(url)) > MAX_URL_LENGTH:
                raise ValueError(
                    f"URL длиннее {MAX_URL_LENGTH} символов: {str(url)[:64]}..."
                )
        return urls
