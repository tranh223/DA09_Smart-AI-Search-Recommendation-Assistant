import json
import os
from datetime import datetime

from dotenv import load_dotenv

from app.db.mongo.mongo_client import get_collection
from app.utils.util import transform_id
from bson import ObjectId
from app.analytics.metrics.evaluator import evaluate_session

try:
    from kafka import KafkaConsumer, KafkaProducer
except ModuleNotFoundError:  # pragma: no cover - optional analytics dependency
    KafkaConsumer = None  # type: ignore[assignment]
    KafkaProducer = None  # type: ignore[assignment]

load_dotenv()

def _normalize_kafka_url(raw_url: str | None) -> str:
    """
    Chuẩn hóa KAFKA_URL từ env để tránh lỗi parse port
    khi có ký tự thừa như dấu "\\" ở cuối.
    """
    if not raw_url:
        return "localhost:9092"
    return raw_url.strip().strip("\"'").rstrip("\\/")


KAFKA_URL = _normalize_kafka_url(os.getenv("KAFKA_URL"))

if KafkaProducer is None:
    producer = None
    print("[Kafka] kafka-python not installed, analytics producer disabled.")
else:
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_URL],
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )
    except Exception as e:
        producer = None
        print(f"[Kafka] Producer init failed with KAFKA_URL='{KAFKA_URL}': {e}")

def producer_send(session_id: str, value):
    if producer is None:
        print("[Kafka] Producer unavailable, skip analytics event.")
        return False
    producer.send(
        topic='users-topic',
        key=session_id.encode('utf-8'),
        value=value
    ).get(timeout=10)
    return True
    
def end_session(session_id: str):
    value = {
        "session_id": session_id,
        "type": "SESSION_END",
        "log": datetime.now().isoformat()
    }
    producer_send(session_id, value)
    if producer is not None:
        producer.flush(timeout=1)
    
def log_chat(question: str, answer: str, session_id: str):
    '''
    log lại cặp câu hỏi - trả lời giữa user - bot (chỉ khi gọi tool RAG)
    '''
    value = {
        "session_id": session_id,
        "type": "RAG_CHAT",
        "log": {
            'user_query': question,
            'llm_answer': answer
        }
    }
    producer_send(session_id, value)

def log_reaction(reaction: bool, session_id: str):
    '''
    log lại số lượng like/dislike trong phiên chat
    '''
    value = {
        "session_id": session_id,
        "type": "REACTION",
        "log": reaction
    }
    producer_send(session_id, value)

def log_final_reaction(final_reaction: bool, session_id: str):
    '''
    log lại like/dislike tổng thể cuối phiên chat
    '''
    value = {
        "session_id": session_id,
        "type": "FINAL_REACTION",
        "log": final_reaction
    }
    producer_send(session_id, value)

def log_latency(time: float, session_id: str):
    '''
    log lại thời gian của 1 LẦN phản hồi của bot trong phiên
    '''
    value = {
        "session_id": session_id,
        "type": "LATENCY",
        "log": time
    }
    producer_send(session_id, value)

def log_ttft(time: float, session_id: str):
    '''
    log lại time to first token của 1 LẦN phản hồi của bot trong phiên
    '''
    value = {
        "session_id": session_id,
        "type": "TTFT",
        "log": time
    }
    producer_send(session_id, value)

def log_booking(session_id: str):
    '''
    log lại việc bấm nút booking
    '''
    value = {
        "session_id": session_id,
        "type": "BOOKING",
        "log": True
    }
    producer_send(session_id, value)

def start_log_listener():
    if KafkaConsumer is None:
        print("[Kafka] kafka-python not installed, skip listener.")
        return
    if not KAFKA_URL:
        print("[Kafka] Missing KAFKA_URL, skip listener.")
        return
    try:
        consumer = KafkaConsumer(
            'users-topic',
            bootstrap_servers=[KAFKA_URL],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='backend-log-processor'
        )
    except Exception as e:
        print(f"[Kafka] Consumer init failed with KAFKA_URL='{KAFKA_URL}': {e}")
        return
    sessions_collection = get_collection("Sessions")
    print("[Kafka] Listener started.")
    for message in consumer:
        try:
            log_data = message.value
            session_id = transform_id(log_data.get("session_id"))
            msg_type = log_data.get("type")
            log = log_data.get('log')
            filter_query = {"_id": session_id}
            update_query = {}
            default_fields = {
                "history": [],
                "num_like": 0,
                "num_dislike": 0,
                "final_reaction": None,
                "latency": [],
                "ttft": [],
                "booking": False,
                "evaluated": False,
                "end": None  
            }
            if msg_type != 'SESSION_END':
                if msg_type == 'RAG_CHAT':
                    update_query = {
                        "$push": {
                            "history": {
                                "user_query": log.get("user_query"),
                                "llm_answer": log.get("llm_answer")
                            }
                        }
                    }
                    default_fields.pop("history", None)
                elif msg_type == 'REACTION':
                    if log is True:
                        update_query = {"$inc": {"num_like": 1}}
                        default_fields.pop("num_like", None)
                    else:
                        update_query = {"$inc": {"num_dislike": 1}}
                        default_fields.pop("num_dislike", None)
                elif msg_type == 'FINAL_REACTION':
                    update_query = {"$set": {"final_reaction": log}}
                    default_fields.pop("final_reaction", None)
                elif msg_type == 'LATENCY':
                    update_query = {"$push": {"latency": log}}
                    default_fields.pop("latency", None)
                elif msg_type == 'TTFT':
                    update_query = {"$push": {"ttft": log}}
                    default_fields.pop("ttft", None)
                elif msg_type == 'BOOKING':
                    update_query = {"$set": {"booking": log}}
                    default_fields.pop("booking", None)
                if update_query:
                    update_query["$setOnInsert"] = default_fields
                    sessions_collection.update_one(filter_query, update_query, upsert=True)
                    print(f"[Kafka] Updated {msg_type} for session: {session_id}")
            else:
                end_time = datetime.fromisoformat(log) if isinstance(log, str) else datetime.now()
                default_fields.pop("end", None)
                update_query = {
                    "$set": {"end": end_time},
                    "$setOnInsert": default_fields
                }
                sessions_collection.update_one(filter_query, update_query, upsert=True)
                print(f"[Kafka] Evaluate session: {session_id}")
                evaluate_session(session_id=session_id)
        except Exception as e:
            print(f"[Log] Message processing error: {str(e)}")

def log_booking_for_graph(hotel_id, user_id, hotel_name):
    '''
    lưu user bấm booking khách sạn nào (để tăng weight trong graphDB)
    '''
    bookings_collection = get_collection('Booking')
    booking_data = {
        "user_id": transform_id(user_id),
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "booked_at": datetime.now()
    }
    try:
        result = bookings_collection.insert_one(booking_data)
        print(f"[Mongo] Booking logged. ID: {result.inserted_id}")
        return result.inserted_id
    except Exception as e:
        print(f"[Mongo] Booking log error: {str(e)}")
        return None
    

def clear_log(session_id: str, collection):
    '''
    xóa reaction, final reaction, latency, ttft, booking của phiên chat sau khi đánh giá
    '''
    collection.update_one(
        {"_id": ObjectId(session_id)},
        {
            "$unset": {
                "num_like": "",
                "num_dislike": "",
                "final_reaction": "",
                "latency": "",
                "ttft": "",
                "booking": ""
            }
        }
    )
