from pydantic import BaseModel, PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataBaseConfig(BaseModel):
    url: PostgresDsn
    echo: bool = False
    echo_pool: bool = False
    pool_size: int = 50
    max_overflow: int = 10


class RedisConfig(BaseModel):
    url: RedisDsn
    max_connections: int = 10
    socket_timeout: float = 30.0
    stream: str = "health_checker:tasks"
    dlq_stream: str = "health_checker:tasks:dlq"
    group: str = "health_checker:workers"
    stream_maxlen: int = 10_000
    block_ms: int = 5000
    batch_size: int = 10

    @model_validator(mode="after")
    def check_socket_timeout(self) -> "RedisConfig":
        if self.socket_timeout <= self.block_ms / 1000:
            raise ValueError(
                "socket_timeout должен превышать block_ms: "
                f"{self.socket_timeout}s <= {self.block_ms / 1000}s"
            )
        return self


class WorkerConfig(BaseModel):
    concurrency: int = 10
    request_timeout: float = 10.0
    max_attempts: int = 3
    claim_min_idle_ms: int = 60_000
    claim_interval_s: float = 30.0
    retry_delay_s: float = 2.0


class LogConfig(BaseModel):
    level: str = "INFO"
    json_format: bool = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_nested_delimiter="__",
        env_prefix="APP_CONFIG__",
    )

    db: DataBaseConfig
    redis: RedisConfig
    worker: WorkerConfig = WorkerConfig()
    log: LogConfig = LogConfig()

settings = Settings()
