import argparse
from getpass import getpass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import database_url
from .database import make_engine
from .main import password_hash
from .models import User
from .schemas import Login


def main():
    parser = argparse.ArgumentParser(description="创建教师账号")
    parser.add_argument("username")
    parser.add_argument("--name", required=True, help="教师显示名称")
    args = parser.parse_args()
    name = args.name.strip()
    if not 1 <= len(name) <= 80:
        parser.error("显示名称应为 1–80 个字符")
    password = getpass("密码（12–128 个字符）: ")
    if len(password) < 12 or len(password) > 128 or not password.strip():
        parser.error("密码长度不符合要求")
    if getpass("再次输入密码: ") != password:
        parser.error("两次输入的密码不一致")
    try:
        username = Login(username=args.username, password=password).username
    except ValueError:
        parser.error("用户名应为 3–64 个英文字母、数字、下划线、点或连字符")
    engine = make_engine(database_url())
    try:
        with Session(engine) as db:
            if db.scalar(select(User.id).where(User.username == username)):
                parser.error("用户名已存在")
            db.add(User(username=username, name=name, password_hash=password_hash.hash(password)))
            db.commit()
    finally:
        engine.dispose()
    print("教师账号已创建。")


if __name__ == "__main__":
    main()
