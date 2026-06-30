import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")

client = None
db = None


def connect() -> None:
    """Khởi tạo kết nối MongoDB. Gọi từ lifespan, không chạy ở import time."""
    global client, db
    if client is not None:
        return
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DATABASE_NAME]
        client.server_info()
        print("[MongoDB] Ket noi thanh cong!")
    except PyMongoError as e:
        print(f"[MongoDB] Khong the ket noi: {e}")


def disconnect() -> None:
    """Đóng kết nối MongoDB khi shutdown."""
    global client, db
    if client is not None:
        client.close()
        client = None
        db = None


def get_collection(collection_name: str):
    """Hàm tiện ích để lấy collection bất kỳ. Tự kết nối nếu chưa có."""
    if db is None:
        connect()
    if db is None:
        raise RuntimeError("MongoDB chưa được khởi tạo hoặc không thể kết nối.")
    return db[collection_name]