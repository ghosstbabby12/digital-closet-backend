from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, garments, outfits, weather
from app.core.config import settings
from app.db.session import Base, engine
import app.models  # noqa: F401 - registra los modelos en Base.metadata

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Curador de Moda IA")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.include_router(auth.router)
app.include_router(garments.router)
app.include_router(weather.router)
app.include_router(outfits.router)


@app.get("/health")
def health():
    return {"status": "ok"}
