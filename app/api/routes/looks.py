from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.garment import Garment
from app.models.look import Look
from app.models.user import User
from app.schemas.look import LookGenerateRequest, LookOut
from app.services.storage import (
    delete_look_image,
    look_image_url,
    read_body_photo,
    read_garment_image,
    save_look_image,
)
from app.services.try_on_generation import can_try_on, generate_try_on, wearing_order

router = APIRouter(prefix="/looks", tags=["looks"])


def _to_out(look: Look) -> LookOut:
    return LookOut(
        id=look.id,
        image_url=look_image_url(look.image_path),
        garment_ids=[int(i) for i in look.garment_ids.split(",") if i],
        created_at=look.created_at,
    )


@router.post("", response_model=LookOut, status_code=201)
def generate_look(
    payload: LookGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.body_photo_path:
        raise HTTPException(status_code=400, detail="Primero sube tu foto de cuerpo completo.")

    garment_ids = list(dict.fromkeys(payload.garment_ids))
    garments = (
        db.query(Garment)
        .filter(Garment.id.in_(garment_ids), Garment.owner_id == current_user.id)
        .all()
    )
    if len(garments) != len(garment_ids):
        raise HTTPException(status_code=404, detail="Prenda no encontrada.")
    if any(not g.cutout_path for g in garments):
        raise HTTPException(status_code=400, detail="Pon primero cada prenda en el probador.")
    if any(not can_try_on(g.category) for g in garments):
        raise HTTPException(status_code=400, detail="Los accesorios aún no se pueden probar con IA.")

    ordered = wearing_order(garments)
    ordered_ids = ",".join(str(g.id) for g in ordered)

    # La misma combinación sobre la misma foto ya está hecha: se devuelve al
    # instante y sin gastar créditos.
    existing = (
        db.query(Look)
        .filter(
            Look.owner_id == current_user.id,
            Look.garment_ids == ordered_ids,
            Look.body_photo_path == current_user.body_photo_path,
        )
        .order_by(Look.created_at.desc())
        .first()
    )
    if existing:
        return _to_out(existing)

    # Cada prenda probada gasta un crédito de FASHN: se limita cuántas puede probar cada usuario por día.
    since = datetime.now(timezone.utc) - timedelta(days=1)
    recent = db.query(Look.garment_ids).filter(Look.owner_id == current_user.id, Look.created_at >= since).all()
    used_today = sum(len([i for i in ids.split(",") if i]) for (ids,) in recent)
    if used_today + len(garments) > settings.try_on_daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Llegaste al límite de {settings.try_on_daily_limit} prendas probadas por día. Intenta mañana.",
        )

    image, extension, content_type = generate_try_on(
        read_body_photo(current_user.body_photo_path),
        [(g, read_garment_image(g.cutout_path)) for g in ordered],
    )
    look = Look(
        owner_id=current_user.id,
        image_path=save_look_image(image, extension, content_type),
        garment_ids=ordered_ids,
        body_photo_path=current_user.body_photo_path,
    )
    db.add(look)
    db.commit()
    db.refresh(look)
    return _to_out(look)


@router.get("", response_model=list[LookOut])
def list_looks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    looks = db.query(Look).filter(Look.owner_id == current_user.id).order_by(Look.created_at.desc()).all()
    return [_to_out(look) for look in looks]


@router.delete("/{look_id}", status_code=204)
def delete_look(look_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    look = db.query(Look).filter(Look.id == look_id, Look.owner_id == current_user.id).first()
    if not look:
        raise HTTPException(status_code=404, detail="Look no encontrado.")
    delete_look_image(look.image_path)
    db.delete(look)
    db.commit()
