from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20

    jwt_issuer: str
    jwt_audience: str

    service_name: str = "inventory-services"
    service_port: int = 8000
    log_level: str = "INFO"

    rate_limit_rpm: int = 60

    kafka_enabled: bool = False
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_inventory_rates: str = "inventory-rate-events"


settings = Settings()
