from app.db.mongo.mongo_client import get_collection

import calendar

# # def analysis_by_day(month: int):
#     eval_collection = get_collection("Eval")
#     csat  = []
#     latency = []
#     ttft = []
#     booking = []
#     ragas = {
#         "date": [],
#         "faithfulness": [],
#         "answer_relevance": [],
#         "context_precision": [],
#         "context_recall": [],
#     }
#     for doc in eval_collection.find({"date": {"$regex": f"2026-{month:02d}-"}}):
#         print(doc)
#         csat.append(sum(doc.get("csat"))/len(doc.get("csat")))
#         latency.append(sum(doc.get("latency"))/len(doc.get("latency")))
#         ttft.append(sum(doc.get("ttft"))/len(doc.get("ttft")))
#         booked = 0
#         book = doc.get("booking")
#         for b in book:
#             if b == True:
#                 booked += 1
#         booking.append(booked/len(book))
#         if "ragas" in doc:
#             print(doc["ragas"])
#             ragas["date"].append(doc.get("date"))
#             ragas["faithfulness"].append(doc["ragas"].get("faithfulness"))
#             ragas["answer_relevance"].append(doc["ragas"].get("answer_relevancy"))
#             ragas["context_precision"].append(doc["ragas"].get("context_precision"))
#             ragas["context_recall"].append(doc["ragas"].get("context_recall"))

    
#     return {
#         "csat": csat,
#         "ragas": ragas,
#         "latency": latency,
#         "ttft": ttft,
#         "booking": booking
#     }


def analysis_by_day(month: int, year: int = 2026):
    eval_collection = get_collection("Eval")

    # Lấy hết document trong tháng, đánh index theo "date" để tra cứu nhanh
    docs_by_date = {
        doc["date"]: doc
        for doc in eval_collection.find({"date": {"$regex": f"{year}-{month:02d}-"}})
    }

    csat = []
    latency = []
    ttft = []
    booking = []
    ragas = {
        "date": [],
        "faithfulness": [],
        "answer_relevance": [],
        "context_precision": [],
        "context_recall": [],
    }

    num_days = calendar.monthrange(year, month)[1]

    for day in range(1, num_days + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        doc = docs_by_date.get(date_str)

        if doc is None:
            csat.append(0)
            latency.append(0)
            ttft.append(0)
            booking.append(0)
            continue

        csat_list = doc.get("csat") or []
        latency_list = doc.get("latency") or []
        ttft_list = doc.get("ttft") or []
        booking_list = doc.get("booking") or []

        csat.append(sum(csat_list) / len(csat_list) if csat_list else 0)
        latency.append(sum(latency_list) / len(latency_list) if latency_list else 0)
        ttft.append(sum(ttft_list) / len(ttft_list) if ttft_list else 0)

        if booking_list:
            booked = sum(1 for b in booking_list if b is True)
            booking.append(booked / len(booking_list))
        else:
            booking.append(0)

        if "ragas" in doc:
            ragas["date"].append(doc.get("date"))
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

def analysis_by_month(year: int):
    '''
    lấy trong mongodb mọi kết quả đánh giá của năm hiện tại hoặc năm trước đó
    tính toán và trả về số liệu thống kê theo từng tháng trong năm
    output: gần giống của hàm analysis_by_day
    '''
    eval_collection = get_collection("Eval")
    months = []
    csat_month  = []
    latency_month = []
    ttft_month = []
    booking_month = []
    ragas_month = {
        "faithfulness": [],
        "answer_relevance": [],
        "context_precision": [],
        "context_recall": [],
    }

    for month in range(1, 13):
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
           
            for doc in eval_collection.find({"date": {"$regex": f"{year}-{month:02d}-"}}):
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
            
            
            months.append(month)
            csat_month.append(sum(csat)/len(csat) if len(csat) > 0 else 0)
            latency_month.append(sum(latency)/len(latency) if len(latency) > 0 else 0)
            ttft_month.append(sum(ttft)/len(ttft) if len(ttft) > 0 else 0)
            booking_month.append(sum(booking)/len(booking) if len(booking) > 0 else 0)
            ragas_month["faithfulness"].append(sum(ragas["faithfulness"])/len(ragas["faithfulness"]) if len(ragas["faithfulness"]) > 0 else 0)
            ragas_month["answer_relevance"].append(sum(ragas["answer_relevance"])/len(ragas["answer_relevance"]) if len(ragas["answer_relevance"]) > 0 else 0)
            ragas_month["context_precision"].append(sum(ragas["context_precision"])/len(ragas["context_precision"]) if len(ragas["context_precision"]) > 0 else 0)
            ragas_month["context_recall"].append(sum(ragas["context_recall"])/len(ragas["context_recall"]) if len(ragas["context_recall"]) > 0 else 0)
    
    return {
        "months": months,
        "csat": csat_month,
        "latency": latency_month,
        "ttft": ttft_month,
        "booking": booking_month,
        "ragas": ragas_month
    }

# print(analysis_by_month(2026))

# print(analysis_by_day(5))
