from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    komoot_email: str
    komoot_password: str
    hammerhead_email: str
    hammerhead_password: str
    hammerhead_user_id: str
    db_path: str = "./komoot_hammerhead.db"
    api_secret: str = ""
    komoot_tour_type: str = "tour_planned"
    sync_days: int = 3


settings = Settings()
