from backend.app.db.mongo.mongo_client import get_collection

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