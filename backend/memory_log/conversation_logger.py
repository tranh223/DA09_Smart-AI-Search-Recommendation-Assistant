def summarize_chat(summary: str, history: list):
    '''
    cần kiểm tra trước xem có cần summarize k, nếu summary thay đổi thì update summary trong mongodb
    output: new_summary, new_history
    '''
    pass

def update_summary(summary: str, user_id: str):
    '''
    khi update lưu kèm timestamp
    chờ bên DATA setup code mongodb & chốt schema,...  cho collection summaries
    '''
    pass

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

