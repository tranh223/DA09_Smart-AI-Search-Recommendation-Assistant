from dotenv import load_dotenv
from openai import OpenAI
from app.db.mongo.mongo_client import get_collection
import os
from bson import ObjectId
from pymongo.errors import PyMongoError
from datetime import datetime

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_CHAT_BASE_URL") or os.getenv("BASE_URL"),
)

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
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=float(os.getenv("SUMMARY_LLM_TEMPERATURE", "0.3") or "0.3"),
            timeout=float(os.getenv("SUMMARY_LLM_TIMEOUT_SECONDS", os.getenv("LLM_TIMEOUT_SECONDS", "30")) or "30"),
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
