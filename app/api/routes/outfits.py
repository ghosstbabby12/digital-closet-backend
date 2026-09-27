from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.garment import Garment
from app.models.outfit import Outfit
from app.models.user import User
from app.schemas.garment import GarmentOut
from app.schemas.outfit import OutfitGenerateRequest, OutfitOut
from app.services.outfit_advisor import get_outfit_advisor
from app.services.storage import image_path_to_url
from app.services.weather_service import get_current_weather

router = APIRouter(prefix="/outfits", tags=["outfits"])


def _to_out(outfit: Outfit) -> OutfitOut:
    return OutfitOut(
        id=outfit.id,
        occasion=outfit.occasion,
        weather_temp_c=outfit.weather_temp_c,
        weather_condition=outfit.weather_condition,
        explanation=outfit.explanation,
        garments=[
            GarmentOut(
                id=g.id,
                name=g.name,
                category=g.category,
                color=g.color,
                warmth=g.warmth,
                image_url=image_path_to_url(g.image_path),
                created_at=g.created_at,
            )
            for g in outfit.garments
        ],
        created_at=outfit.created_at,
    )


@router.post("/generate", response_model=OutfitOut, status_code=201)
async def generate_outfit(
    payload: OutfitGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    weather = await get_current_weather(payload.lat, payload.lon)

    garments = db.query(Garment).filter(Garment.owner_id == current_user.id).all()

    advisor = get_outfit_advisor()
    try:
        suggestion = advisor.suggest(garments=garments, weather=weather, occasion=payload.occasion)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    outfit = Outfit(
        owner_id=current_user.id,
        occasion=payload.occasion,
        weather_temp_c=weather.temp_c,
        weather_condition=weather.condition,
        explanation=suggestion.explanation,
        garments=suggestion.garments,
    )
    db.add(outfit)
    db.commit()
    db.refresh(outfit)
    return _to_out(outfit)


@router.get("", response_model=list[OutfitOut])
def list_outfits(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    outfits = (
        db.query(Outfit)
        .filter(Outfit.owner_id == current_user.id)
        .order_by(Outfit.created_at.desc())
        .all()
    )
    return [_to_out(o) for o in outfits]
