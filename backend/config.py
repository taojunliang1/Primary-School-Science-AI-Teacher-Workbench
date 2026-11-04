import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def database_url() -> str:
    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("请在 .env 中设置 DATABASE_URL。")
    if make_url(url).drivername not in {"mysql+pymysql", "sqlite", "sqlite+pysqlite"}:
        raise RuntimeError("请使用 mysql+pymysql 数据库 URL，或使用 SQLite 进行开发测试。")
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    serve_frontend: bool = True
    deepseek_api_key: str = field(default="", repr=False)

    @classmethod
    def from_env(cls):
        url = database_url()
        secret = os.getenv("JWT_SECRET", "")
        if len(secret.encode()) < 32 or secret.startswith("REPLACE_"):
            raise RuntimeError("请在 .env 中设置至少 32 字节的随机 JWT_SECRET。")
        return cls(url, secret, deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip())
