from datasets import Dataset
from openai import OpenAI
import os
import random
from datetime import datetime
from app.db.mongo.mongo_client import get_collection
from bson import ObjectId
from app.utils.util import transform_id

try:
    from ragas import evaluate
    from ragas.llms import llm_factory
    from ragas.embeddings import OpenAIEmbeddings
    HAS_RAGAS = True
except ImportError:
    evaluate = None
    llm_factory = None
    OpenAIEmbeddings = None
    HAS_RAGAS = False


def _ragas_openai_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_CHAT_BASE_URL") or os.getenv("BASE_URL"),
    )


def _ragas_model() -> str:
    return os.getenv("LLM_MODEL", "gpt-4o-mini")


def _ensure_ragas_available():
    if not HAS_RAGAS:
        raise RuntimeError(
            "Ragas is not installed. Install it with `pip install ragas` to use ragas evaluation."
        )

def ragas_at_deploy(questions: list, ground_truths: list, llm_answers: list, contexts_list: list) -> dict:
    """
    chạy ragas trước khi deploy bằng golden dataset (hỏi DATA)
    output: 4 metric ragas (đơn vị %)
    """
    _ensure_ragas_available()
    dataset = Dataset.from_dict({
        "question": questions,
        "answer": llm_answers,
        "contexts": contexts_list,
        "ground_truth": ground_truths
    })
    custom_client = _ragas_openai_client()
    ragas_llm = llm_factory(model=_ragas_model(), client=custom_client)
    ragas_emb = OpenAIEmbeddings(client=custom_client)
    if hasattr(ragas_emb, 'embed_text'):
        ragas_emb.embed_query = ragas_emb.embed_text
        ragas_emb.embed_documents = lambda texts: [ragas_emb.embed_text(t) for t in texts]
    result = evaluate(dataset=dataset, llm=ragas_llm, embeddings=ragas_emb)    
    result = result._scores_dict
    for i in result:
        result[i] = int(sum(result[i]) / len(result[i]) * 10000) / 100
    print(result)
    return result

def ragas_at_weekend():
    '''
    chạy ragas mỗi cuối tuần bằng 5% random trong đống log chat (k vượt quá 30 bộ hỏi-đáp)
    tính xong lưu luôn 4 metric ragas (đơn vị %) vào mongodb
    * chỉ lấy random từ những session mà có end < now() và evaluated = true, chạy xong xóa session
    '''
    _ensure_ragas_available()
    sessions_collection = get_collection('Sessions')
    evals_collection = get_collection('Eval')
    now = datetime.now()
    query_filter = {
        "end": {"$lt": now},
        "evaluated": True
    }
    valid_sessions = list(sessions_collection.find(query_filter))
    if not valid_sessions:
        print("📭 [Ragas Weekend] Không có session nào thỏa mãn điều kiện lọc.")
        return
    all_chat_pairs = []
    session_ids_to_delete = []
    for session in valid_sessions:
        session_ids_to_delete.append(transform_id(session["_id"]))
        for chat in session.get("history", []):
            if "user_query" in chat and "llm_answer" in chat and "contexts" in chat:
                all_chat_pairs.append({
                    "question": chat["user_query"],
                    "answer": chat["llm_answer"],
                    "contexts": chat["contexts"]
                })
    if not all_chat_pairs:
        print("📭 [Ragas Weekend] Các session hợp lệ không chứa dữ liệu lịch sử chat hợp lệ.")
        return
    sample_size = max(1, int(len(all_chat_pairs) * 0.05))
    sample_size = min(sample_size, 30)
    sampled_chats = random.sample(all_chat_pairs, sample_size)
    print(f"🔄 [Ragas Weekend] Đang tiến hành đánh giá trên {len(sampled_chats)} mẫu chat ngẫu nhiên...")
    questions = [c["question"] for c in sampled_chats]
    llm_answers = [c["answer"] for c in sampled_chats]
    contexts_list = [c["contexts"] for c in sampled_chats]
    ground_truths = [""] * len(questions)
    dataset = Dataset.from_dict({
        "question": questions,
        "answer": llm_answers,
        "contexts": contexts_list,
        "ground_truth": ground_truths
    })
    custom_client = _ragas_openai_client()
    ragas_llm = llm_factory(model=_ragas_model(), client=custom_client)
    ragas_emb = OpenAIEmbeddings(client=custom_client)
    if hasattr(ragas_emb, 'embed_text'):
        ragas_emb.embed_query = ragas_emb.embed_text
        ragas_emb.embed_documents = lambda texts: [ragas_emb.embed_text(t) for t in texts]
    result = evaluate(dataset=dataset, llm=ragas_llm, embeddings=ragas_emb)    
    result = result._scores_dict
    for i in result:
        result[i] = int(sum(result[i]) / len(result[i]) * 10000) / 100
    today_str = now.strftime("%Y-%m-%d")
    evals_collection.update_one(
        {"date": today_str},
        {"$set": {"ragas": result}},
        upsert=True
    )
    if session_ids_to_delete:
        delete_result = sessions_collection.delete_many({"_id": {"$in": session_ids_to_delete}})
        print(f"🗑️ [Ragas Weekend] Đã xóa {delete_result.deleted_count} session cũ khỏi database.")


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
