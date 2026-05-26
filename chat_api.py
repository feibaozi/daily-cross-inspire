import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.chat_engine import ChatEngine
from src.ai_summarizer import AISummarizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("chat_api")

app = FastAPI(title="DailyCrossInspire Chat API")

chat_engine: ChatEngine = None


@app.on_event("startup")
async def startup():
    global chat_engine
    ai_config = _load_ai_config()
    summarizer = AISummarizer(
        api_base=ai_config["api_base"],
        api_key=ai_config["api_key"],
        model=ai_config.get("model", "deepseek-chat"),
    )
    chat_engine = ChatEngine(ai_summarizer=summarizer, cache_db_path="data/cache.db")
    logger.info("Chat engine initialized")


def _load_ai_config() -> dict:
    import yaml
    import re
    base = Path(__file__).resolve().parent
    settings_path = base / "config" / "settings.yaml"
    with open(settings_path, "r", encoding="utf-8") as f:
        raw = f.read()
    for var_name in re.findall(r"\$\{(\w+)\}", raw):
        raw = raw.replace(f"${{{var_name}}}", os.environ.get(var_name, ""))
    settings = yaml.safe_load(raw)
    return settings["ai"]


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "message is required"}, status_code=400)

    reply = await chat_engine.chat(message)
    return {"reply": reply}


@app.post("/chat/clear")
async def clear_history():
    chat_engine.clear_history()
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("CHAT_API_PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)