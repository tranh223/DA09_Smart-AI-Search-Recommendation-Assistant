import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")

client = None
db = None

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DATABASE_NAME]
    client.server_info()
    print("🚀 [MongoDB] Kết nối thành công!")
except PyMongoError as e:
    print(f"❌ [MongoDB] Không thể kết nối: {e}")


def get_collection(collection_name: str):
    """Hàm tiện ích để lấy collection bất kỳ."""
    if db is None:
        raise RuntimeError("MongoDB driver chưa được khởi tạo.")
    return db[collection_name]