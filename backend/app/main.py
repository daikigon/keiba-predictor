from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import setup_logging, get_logger
from app.api.routes import races, predictions, history, data, stats, model, horses, jockeys

# ログ設定の初期化
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Keiba Predictor API",
    description="中央競馬予想アプリ API",
    version="0.1.0",
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(races.router, prefix="/api/v1/races", tags=["races"])
app.include_router(predictions.router, prefix="/api/v1/predictions", tags=["predictions"])
app.include_router(history.router, prefix="/api/v1/history", tags=["history"])
app.include_router(data.router, prefix="/api/v1/data", tags=["data"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["stats"])
app.include_router(model.router, prefix="/api/v1/model", tags=["model"])
app.include_router(horses.router, prefix="/api/v1/horses", tags=["horses"])
app.include_router(jockeys.router, prefix="/api/v1/jockeys", tags=["jockeys"])


@app.on_event("startup")
async def startup_event():
    logger.info("Keiba Predictor API starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Keiba Predictor API shutting down...")


@app.get("/")
async def root():
    return {"message": "Keiba Predictor API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
