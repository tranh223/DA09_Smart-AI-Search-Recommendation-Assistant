from datetime import datetime
from pymongo.errors import PyMongoError
from mongo_client import get_collection
from bson import ObjectId
from openai import OpenAI
import os
from dotenv import load_dotenv
import json
from kafka import KafkaProducer, KafkaConsumer
from memory_log.analytic_manager import evaluate_session

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv('BASE_URL'))

KAFKA_URL = os.getenv('KAFKA_URL')
producer = KafkaProducer(
    bootstrap_servers=[KAFKA_URL],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def transform_id(id: str or ObjectId):
    _id = id
    if isinstance(id, str) and ObjectId.is_valid(id):
        _id = ObjectId(id)
    return _id

def summarize_chat(summary: str, history: list, user_id: str) -> tuple[str, list]:
    '''
    cần kiểm tra trước xem có cần summarize k, nếu summary thay đổi thì update summary trong mongodb
    output: new_summary, new_history
    '''
    TRIGGER_THRESHOLD = 6
    if len(history) < TRIGGER_THRESHOLD:
        return summary, history    
    # system_prompt = (
    #     "Bạn là một trợ lý AI chuyên nghiệp có nhiệm vụ quản lý bộ nhớ hội thoại. "
    #     "Hãy cập nhật đoạn tóm tắt (Summary) cũ bằng cách tích hợp thêm các thông tin quan trọng từ đoạn hội thoại mới (New Chat). "
    #     "Yêu cầu: Chỉ giữ lại các thông tin cốt lõi về nhu cầu, sở thích, ngân sách, lưu ý đặc biệt của khách hàng. "
    #     "Đoạn tóm tắt mới phải ngắn gọn, súc tích và viết bằng Tiếng Việt."
    # )
    system_prompt = (
        "Bạn là một trợ lý AI chuyên nghiệp quản lý bộ nhớ hội thoại cho hệ thống OTA.\n"
        "Nhiệm vụ của bạn là tổng hợp và cập nhật đoạn tóm tắt (Summary) cũ bằng cách tích hợp thêm các thông tin quan trọng từ đoạn hội thoại mới (History).\n\n"
        
        "QUY TẮC NÉN DỮ LIỆU:\n"
        "- Chỉ giữ lại các thông tin cốt lõi như: nhu cầu, sở thích, thói quen, ngân sách, thời gian, lưu ý đặc biệt,... của khách hàng.\n"
        "- Đoạn tóm tắt mới viết bằng tiếng Việt, tổng độ dài KHÔNG ĐƯỢC QUÁ 250 từ.\n"
        "- Chỉ giữ lại dữ liệu thực tế, loại bỏ hoàn toàn lời chào hỏi, từ thừa.\n"
        "- Nếu thông tin ở hội thoại mới phủ định thông tin cũ (ví dụ: khách đổi ý), hãy cập nhật lại thông tin mới nhất."
    )
    user_prompt = f"""
    --- SUMMARY CŨ ---
    {summary if summary else "Chưa có thông tin tóm tắt trước đó."}
    
    --- ĐOẠN HỘI THOẠI MỚI CẦN CẬP NHẬT ---
    {history}
    
    Hãy trả ra đoạn Summary mới hoàn chỉnh sau khi đã gộp dữ liệu:
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        new_summary = response.choices[0].message.content.strip()        
        if new_summary != summary:
            db_status = update_summary(summary=new_summary, user_id=user_id)
            if db_status:
                print("✅ [summarize_chat] Đã cập nhật Summary mới vào MongoDB thành công.")
            else:
                print("❌ [summarize_chat] Hàm update_summary báo lỗi DB, nhưng vẫn trả về summary mới cho runtime.")        
        new_history = [] 
        return new_summary, new_history
    except Exception as e:
        print(f"❌ [summarize_chat] Lỗi khi gọi OpenAI API: {str(e)}")
        return summary, history

def update_summary(summary: str, user_id: str or ObjectId) -> bool:
    '''
    khi update lưu kèm timestamp
    '''
    try:
        summaries_collection = get_collection("Summary")
        db_user_id = user_id
        if isinstance(user_id, str) and ObjectId.is_valid(user_id):
            db_user_id = ObjectId(user_id)
        filter_query = {"user_id": db_user_id}  
        update_data = {
            "$set": {
                "content": summary,
                "last_updated": datetime.now()
            }
        }
        result = summaries_collection.update_one(filter_query, update_data, upsert=True)
        if result.upserted_id:
            print(f"🔹 [update_summary] Đã tạo mới Summary cho User ID: {user_id}")
        else:
            print(f"🔹 [update_summary] Đã cập nhật Summary cho User ID: {user_id}")
        return True
    except PyMongoError as e:
        print(f"❌ [update_summary] Lỗi thao tác MongoDB với user {user_id}: {str(e)}")
        return False
    
def producer_send(session_id: str, value):
    producer.send(
        topic='users-topic', 
        key=session_id.encode('utf-8'), 
        value=value
    ).get(timeout=10)
    
def end_session(session_id: str):
    value = {
        "session_id": session_id,
        "type": "SESSION_END",
        "log": datetime.now().isoformat()
    }
    producer_send(session_id, value)
    producer.flush()
    
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
    consumer = KafkaConsumer(
        'users-topic',
        bootstrap_servers=[KAFKA_URL],
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='backend-log-processor'
    )
    sessions_collection = get_collection("Sessions")
    print("📥 Kafka Listener bắt đầu chạy...")
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
                    print(f"💾 Cập nhật {msg_type} thành công cho session: {session_id}")
            else:
                end_time = datetime.fromisoformat(log) if isinstance(log, str) else datetime.now()
                default_fields.pop("end", None)
                update_query = {
                    "$set": {"end": end_time},
                    "$setOnInsert": default_fields
                }
                sessions_collection.update_one(filter_query, update_query, upsert=True)
                print(f"🔔 Đánh giá phiên: {session_id}")
                evaluate_session(session_id=session_id)
        except Exception as e:
            print(f"❌ [Log] Lỗi xử lý tin nhắn: {str(e)}")

def ragas_at_deploy(golden_dataset: list) -> dict:
    '''
    chạy ragas trước khi deploy bằng golden dataset (hỏi DATA)
    output: 4 metric ragas (đơn vị %)
    '''
    pass

def ragas_at_weekend():
    '''
    chạy ragas mỗi cuối tuần bằng 5% random trong đống log chat (k vượt quá 30 bộ hỏi-đáp)
    tính xong lưu luôn 4 metric ragas (đơn vị %) vào mongodb
    * chỉ lấy random từ những session mà có end < now() và evaluated = true, chạy xong xóa session
    '''
    pass