from app.db.mongo.mongo_client import get_collection
from datetime import datetime
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

# apply for gpt-4o-mini (unit: $)
COST_PER_INPUT_TOKEN = 0.15 / 1000000
COST_PER_OUTPUT_TOKEN = 0.6 / 1000000

def analysis_by_day(month: int):
    year = datetime.now().year
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
    input_token = []
    output_token = []

    num_days = calendar.monthrange(year, month)[1]

    for day in range(1, num_days + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        doc = docs_by_date.get(date_str)

        if doc is None:
            csat.append(0)
            latency.append(0)
            ttft.append(0)
            booking.append(0)
            input_token.append(0)
            output_token.append(0)
            continue

        csat_list = doc.get("csat") or []
        latency_list = doc.get("latency") or []
        ttft_list = doc.get("ttft") or []
        booking_list = doc.get("booking") or []
        input_token_lst = doc.get('input_token', [])
        output_token_lst = doc.get('output_token', [])

        csat.append(round(sum(csat_list) / len(csat_list) * 100, 2) if csat_list else 0)
        latency.append(round(sum(latency_list) / len(latency_list), 2) if latency_list else 0)
        ttft.append(round(sum(ttft_list) / len(ttft_list), 2) if ttft_list else 0)
        input_token.append(round(sum(input_token_lst) / len(input_token_lst), 2) if input_token_lst else 0)
        output_token.append(round(sum(output_token_lst) / len(output_token_lst), 2) if output_token_lst else 0)

        if booking_list:
            booked = sum(1 for b in booking_list if b is True)
            booking.append(round(booked / len(booking_list) * 100, 2))
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
        "booking": booking,
        'input_token': input_token,
        'output_token': output_token,
        'input_token_cost': [round(i * COST_PER_INPUT_TOKEN, 2) for i in input_token],
        'output_token_cost': [round(i * COST_PER_OUTPUT_TOKEN, 2) for i in output_token]
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
    input_token_month = []
    output_token_month = []

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
        input_token = []
        output_token = []
        
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
            input_token += doc.get('input_token', [])
            output_token += doc.get('output_token', [])
        
        months.append(month)
        csat_month.append(round(sum(csat)/len(csat) * 100, 2) if len(csat) > 0 else 0)
        latency_month.append(round(sum(latency)/len(latency), 2) if len(latency) > 0 else 0)
        ttft_month.append(round(sum(ttft)/len(ttft), 2) if len(ttft) > 0 else 0)
        booking_month.append(round(sum(booking)/len(booking) * 100, 2) if len(booking) > 0 else 0)
        ragas_month["faithfulness"].append(sum(ragas["faithfulness"])/len(ragas["faithfulness"]) if len(ragas["faithfulness"]) > 0 else 0)
        ragas_month["answer_relevance"].append(sum(ragas["answer_relevance"])/len(ragas["answer_relevance"]) if len(ragas["answer_relevance"]) > 0 else 0)
        ragas_month["context_precision"].append(sum(ragas["context_precision"])/len(ragas["context_precision"]) if len(ragas["context_precision"]) > 0 else 0)
        ragas_month["context_recall"].append(sum(ragas["context_recall"])/len(ragas["context_recall"]) if len(ragas["context_recall"]) > 0 else 0)
        input_token_month.append(round(sum(input_token) / len(input_token), 2) if input_token else 0)
        output_token_month.append(round(sum(output_token) / len(output_token), 2) if output_token else 0)
    
    return {
        "months": months,
        "csat": csat_month,
        "latency": latency_month,
        "ttft": ttft_month,
        "booking": booking_month,
        "ragas": ragas_month,
        'input_token': input_token_month,
        'output_token': output_token_month,
        'input_token_cost': [round(i * COST_PER_INPUT_TOKEN, 2) for i in input_token_month],
        'output_token_cost': [round(i * COST_PER_OUTPUT_TOKEN, 2) for i in output_token_month]
    }

# print(analysis_by_month(2026))

# print(analysis_by_day(5))
