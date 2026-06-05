def clear_log(session_id: str):
    '''
    xóa reaction, final reaction, latency, ttft của phiên chat sau khi đánh giá, chờ DATA
    * KHÔNG xóa log chat
    '''
    pass

def save_evaluation_result(session_id: str, csat: float, average_latency: float, average_ttft: float):
    '''
    lưu CSAT, average latency, TTFT của 1 phiên vào mongodb, chờ DATA
    * cái đầu lưu ở đơn vị %, 2 cái sau là giây
    '''
    pass

def session_csat(session_id: str):
    '''
    tính csat cho 1 phiên
    output: csat theo dạng %
    '''
    pass

def session_average_latency(session_id: str):
    '''
    tính latency trung bình của cả 1 phiên
    output: float (giây)
    '''
    pass

def session_average_ttft(session_id: str):
    '''
    tính ttft trung bình của cả 1 phiên
    output: float (giây)
    '''
    pass

def analysis_by_day(month: int):
    '''
    lấy trong mongodb mọi kết quả đánh giá của 1 tháng cụ thể trong năm hiện tại
    tính toán và trả về số liệu thống kê theo từng ngày trong tháng
    output: {
        "csat": [], 
        "ragas": {
            "faithfulness": [],
            "answer_relevance": [],
            "context_precision": [],
            "context_recall": [],
        }, (chỉ có data vào các ngày CN)
        "latency": [],
        "ttft": []
    }
    '''
    pass

def analysis_by_month(year: int):
    '''
    lấy trong mongodb mọi kết quả đánh giá của năm hiện tại hoặc năm trước đó
    tính toán và trả về số liệu thống kê theo từng tháng trong năm
    output: gần giống của hàm analysis_by_day
    '''
    pass