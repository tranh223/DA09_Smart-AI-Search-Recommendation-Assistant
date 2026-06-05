from datetime import datetime
from pymongo.errors import PyMongoError
from mongo_client import get_collection
from bson import ObjectId
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv('BASE_URL'))

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
        "Bạn là một trợ lý AI chuyên nghiệp quản lý bộ nhớ dài hạn của hệ thống.\n"
        "Nhiệm vụ của bạn là tổng hợp và cập nhật đoạn tóm tắt (Summary) cũ bằng cách tích hợp thêm các thông tin quan trọng từ đoạn hội thoại mới (History).\n\n"
        
        "YÊU CẦU CẤU TRÚC ĐẦU RA (Giữ nguyên định dạng Markdown bên dưới):\n"
        "1. [Mục tiêu & Nhu cầu chính]: (Ví dụ: Tìm kiếm thông tin gì, bài toán cần giải quyết...)\n"
        "2. [Tiêu chí kỹ thuật & Ngân sách]: (Ví dụ: Công nghệ sử dụng, giới hạn tài chính, thời gian...)\n"
        "3. [Thông tin bối cảnh khác]: (QUAN TRỌNG: Nơi lưu trữ mọi thông tin phát sinh đột xuất, sở thích, thói quen, lỗi hệ thống gặp phải, hoặc bất kỳ dữ liệu factual nào có ích cho việc duy trì mạch tư vấn dài hạn nhưng không thuộc 2 mục trên).\n\n"
        
        "QUY TẮC NÉN DỮ LIỆU:\n"
        "- Tổng độ dài toàn bộ các mục KHÔNG ĐƯỢC QUÁ 250 từ.\n"
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
    
def log_chat(question: str, answer: str, session_id: str):
    '''
    log lại cặp câu hỏi - trả lời giữa user - bot, chờ DATA xem log vào đâu
    '''
    pass

def log_reaction(reaction: bool, session_id: str):
    '''
    log lại số lượng like/dislike trong phiên chat, chờ DATA xem log vào đâu
    '''
    pass

def log_final_reaction(final_reaction: bool, session_id: str):
    '''
    log lại like/dislike tổng thể cuối phiên chat, chờ DATA
    '''
    pass

def log_latency(time: float, session_id: str):
    '''
    log lại thời gian của 1 LẦN phản hồi của bot trong phiên, chờ DATA
    '''
    pass

def log_ttft(time: float, session_id: str):
    '''
    log lại time to first token của 1 LẦN phản hồi của bot trong phiên, chờ DATA
    '''
    pass

def ragas_at_deploy():
    '''
    chạy ragas trước khi deploy bằng golden dataset (hỏi DATA)
    output: 4 metric ragas (đơn vị %)
    '''
    pass

def ragas_at_weekend():
    '''
    chạy ragas mỗi cuối tuần bằng 5% random trong đống log chat (k vượt quá 30 bộ hỏi-đáp)
    tính xong lưu luôn 4 metric ragas (đơn vị %) vào mongodb (đoạn này cần chờ DATA) & xóa log chat của cả tuần đó
    '''
    pass

