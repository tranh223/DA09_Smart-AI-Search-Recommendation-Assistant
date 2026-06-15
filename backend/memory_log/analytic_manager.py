# def evaluate_session(session_id: str):
#     '''
#     riêng hàm này k thay đổi tham sổ, k xóa (vì file còn lại đang import)
#     vào mongodb lấy hết log của 1 session ra & đánh giá (có thể gọi các hàm ở dưới)
#     '''
#     pass

# def clear_log(session_id: str):
#     '''
#     xóa reaction, final reaction, latency, ttft, booking của phiên chat sau khi đánh giá
#     '''
#     pass

# def save_evaluation_result(session_id: str, csat: float, average_latency: float, average_ttft: float):
#     '''
#     lưu CSAT, average latency, TTFT, booking của 1 phiên vào mongodb & set trường evaluated = true
#     * cái đầu lưu ở đơn vị %, 2 cái sau là giây
#     '''
#     pass

# def session_csat(session_id: str):
#     '''
#     tính csat cho 1 phiên
#     output: csat theo dạng %
#     '''
#     pass

# def session_average_latency(session_id: str):
#     '''
#     tính latency trung bình của cả 1 phiên
#     output: float (giây)
#     '''
#     pass

# def session_average_ttft(session_id: str):
#     '''
#     tính ttft trung bình của cả 1 phiên
#     output: float (giây)
#     '''
#     pass

# def analysis_by_day(month: int):
#     '''
#     lấy trong mongodb mọi kết quả đánh giá của 1 tháng cụ thể trong năm hiện tại
#     tính toán và trả về số liệu thống kê theo từng ngày trong tháng
#     output: {
#         "csat": [], 
#         "ragas": {
#             "faithfulness": [],
#             "answer_relevance": [],
#             "context_precision": [],
#             "context_recall": [],
#         }, (chỉ có data vào các ngày CN, cân nhắc lưu thêm trường date gì đó để biết là kết quả ragas rơi vào những ngày nào)
#         "latency": [],
#         "ttft": [],
#         "booking": []
#     }
#     '''
#     pass

# def analysis_by_month(year: int):
#     '''
#     lấy trong mongodb mọi kết quả đánh giá của năm hiện tại hoặc năm trước đó
#     tính toán và trả về số liệu thống kê theo từng tháng trong năm
#     output: gần giống của hàm analysis_by_day
#     '''
#     pass


from datetime import datetime
from bson import ObjectId

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mongo_client import get_collection

def session_average_latency(session_id: str, collection):
    '''
    tính latency trung bình của cả 1 phiên
    output: float (giây)
    '''
    doc = collection.find_one({"_id": ObjectId(session_id)})

    if doc is None:
        raise ValueError(f"Session {session_id} not found")

    latencies = doc.get("latency", [])

    if not latencies:
        return 0.0

    avg_ms = sum(latencies) / len(latencies)

    return avg_ms 


def session_average_ttft(session_id: str, collection):
    '''
    tính ttft trung bình của cả 1 phiên
    output: float (giây)
    '''
    doc = collection.find_one({"_id": ObjectId(session_id)})

    if doc is None:
        raise ValueError(f"Session {session_id} not found")

    ttfts = doc.get("ttft", [])

    if not ttfts:
        return 0.0

    avg_ms = sum(ttfts) / len(ttfts)

    return avg_ms 


def session_csat(session_id: str, collection):
    '''
    tính csat cho 1 phiên
    output: csat theo dạng %
    '''
    doc = collection.find_one({"_id": ObjectId(session_id)})

    if doc is None:
        raise ValueError(f"Session {session_id} not found")

    num_like = doc.get("num_like", 0)
    num_dislike = doc.get("num_dislike", 0)
    final_reaction = doc.get("final_reaction", None)

    if final_reaction == True:
        final_reaction = 1
    elif final_reaction == False:
        final_reaction = 0

    total = num_like + num_dislike

    if total == 0 & final_reaction is None:
        return None
    
    if final_reaction is None:
        csat = (num_like / total) * 100
    elif total == 0:
        csat = final_reaction * 100
    else:
        csat = (num_like / total) * 0.3 +  final_reaction * 0.7

    return csat


def save_evaluation_result(
    session_id: str,
    csat: float,
    average_latency: float,
    average_ttft: float,
    booking: bool,
    eval_collection,
    sessions_collection
):
    '''
    lưu CSAT, average latency, TTFT, booking của 1 phiên vào mongodb
    & set trường evaluated = true

    csat: %
    average_latency: giây
    average_ttft: giây
    '''

    session = sessions_collection.find_one(
        {"_id": ObjectId(session_id)}
    )

    if session is None:
        raise ValueError(f"Session {session_id} not found")

    if session.get("evaluated", False):
        raise ValueError(f"Session {session_id} already evaluated")

    # booking = session.get("booking", False)

    date_str = datetime.now().strftime("%Y-%m-%d")

    eval_collection.update_one(
        {"date": date_str},
        {
            "$push": {
                "csat": csat,
                "latency": average_latency,
                "ttft": average_ttft,
                "booking": booking
            }
        },
        upsert=True
    )

    sessions_collection.update_one(
        {"_id": ObjectId(session_id)},
        {
            "$set": {
                "evaluated": True
            }
        }
    )

    return True


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


def evaluate_session(session_id: str):
    eval_collection = get_collection("Eval")
    sessions_collection = get_collection("Sessions")

    if sessions_collection.find_one({"_id": ObjectId(session_id)}).get("evaluated", False):
        raise ValueError(f"Session {session_id} already evaluated")

    latency = session_average_latency(session_id, sessions_collection)
    ttft = session_average_ttft(session_id, sessions_collection)
    csat = session_csat(session_id, sessions_collection)
    booking = sessions_collection.find_one({"_id": ObjectId(session_id)}).get("booking", False)

    save_evaluation_result(session_id, csat, latency, ttft, booking, eval_collection, sessions_collection)

    clear_log(session_id, sessions_collection)


def analysis_by_day(month: int):
    '''
    lấy trong mongodb mọi kết quả đánh giá của 1 tháng cụ thể trong năm hiện tại
    tính toán và trả về số liệu thống kê theo từng ngày trong tháng
    output: {
        "csat": [], 
        "ragas": {
            "faithfulness": [],
            "answer_relevancy": [],
            "context_precision": [],
            "context_recall": [],
        }, (chỉ có data vào các ngày CN, cân nhắc lưu thêm trường date gì đó để biết là kết quả ragas rơi vào những ngày nào)
        "latency": [],
        "ttft": [],
        "booking": []
    }
    '''
    eval_collection = get_collection("Eval")
    csat  = []
    latency = []
    ttft = []
    booking = []
    ragas = {
        "faithfulness": [],
        "answer_relevance": [],
        "context_precision": [],
        "context_recall": [],
    }
    for doc in eval_collection.find({"date": {"$regex": f"2026-{month:02d}-"}}):
        print(doc)
        csat.append(sum(doc.get("csat"))/len(doc.get("csat")))
        latency.append(sum(doc.get("latency"))/len(doc.get("latency")))
        ttft.append(sum(doc.get("ttft"))/len(doc.get("ttft")))
        booked = 0
        book = doc.get("booking")
        for b in book:
            if b == True:
                booked += 1
        booking.append(booked/len(book))
        if "ragas" in doc:
            print(doc["ragas"])
            ragas["faithfulness"].append(doc["ragas"].get("faithfulness"))
            ragas["answer_relevance"].append(doc["ragas"].get("answer_relevancy"))
            ragas["context_precision"].append(doc["ragas"].get("context_precision"))
            ragas["context_recall"].append(doc["ragas"].get("context_recall"))

    
    return {
        "csat": csat,
        "ragas": ragas,
        "latency": latency,
        "ttft": ttft,
        "booking": booking
    }


# print('****************************************\n')
# print(analysis_by_day(6))