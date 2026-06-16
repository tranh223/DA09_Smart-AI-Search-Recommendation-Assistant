from fastapi import FastAPI
import threading
from contextlib import asynccontextmanager
from app.analytics.logging.logger import start_log_listener
from app.api.routes.chat import router as chat_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_thread = threading.Thread(target=start_log_listener, daemon=True)
    worker_thread.start()
    yield 

app = FastAPI(lifespan=lifespan)
app.include_router(chat_router)

@app.get("/")
def read_root():
    return {"message": "Still alive"}