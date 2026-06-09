from fastapi import FastAPI
import threading
from contextlib import asynccontextmanager
from memory_log.conversation_logger import start_log_listener

@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_thread = threading.Thread(target=start_log_listener, daemon=True)
    worker_thread.start()
    yield 

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "Still alive"}