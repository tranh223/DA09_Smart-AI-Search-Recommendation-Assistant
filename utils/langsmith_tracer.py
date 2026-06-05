from langsmith import Client, traceable
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class LangSmithTracer:
    """Wrapper cho LangSmith tracing."""
    
    def __init__(self):
        if settings.LANGSMITH_ENABLED and settings.LANGSMITH_API_KEY:
            try:
                self.client = Client(
                    api_key=settings.LANGSMITH_API_KEY
                )
                self.enabled = True
                logger.info("LangSmith tracing enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize LangSmith: {str(e)}")
                self.enabled = False
                self.client = None
        else:
            self.enabled = False
            self.client = None
    
    def trace(self, name: str):
        """Decorator để trace các module."""
        def decorator(func):
            if self.enabled:
                return traceable(name=name)(func)
            else:
                return func
        return decorator
    
    def log_run(self, name: str, inputs: dict, outputs: dict, run_type: str = "chain"):
        """Log một run vào LangSmith."""
        if not self.enabled or not self.client:
            return
        
        try:
            logger.info(f"Logging {name} to LangSmith")
            # LangSmith logging logic sẽ được handled bởi decorator
        except Exception as e:
            logger.warning(f"Error logging to LangSmith: {str(e)}")

tracer = LangSmithTracer()
