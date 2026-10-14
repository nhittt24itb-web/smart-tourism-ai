class Settings:
    DB_HOST: str = "localhost"
    DB_PORT: str = "3306"
    DB_NAME: str = "smart_tourism"
    DB_USERNAME: str = "root"
    DB_PASSWORD: str = ""  
    
    JWT_SECRET: str = "super_secret_jwt_key_smart_tourism_ai_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USERNAME}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

settings = Settings()