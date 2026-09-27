from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.garment import Garment, GarmentCategory, WarmthLevel
from app.models.user import User
from app.schemas.garment import GarmentOut
from app.services.storage import image_path_to_url, save_garment_image

router = APIRouter(prefix="/garments", tags=["garments"])


def _to_out(garment: Garment) -> GarmentOut:
    return GarmentOut(
        id=garment.id,
        name=garment.name,
        category=garment.category,
        color=garment.color,
        warmth=garment.warmth,
        image_url=image_path_to_url(garment.image_path),
        created_at=garment.created_at,
    )


@router.get("", response_model=list[GarmentOut])
def list_garments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    garments = db.query(Garment).filter(Garment.owner_id == current_user.id).order_by(Garment.created_at.desc()).all()
    return [_to_out(g) for g in garments]


@router.post("", response_model=GarmentOut, status_code=201)
def create_garment(
    category: GarmentCategory = Form(...),
    color: str = Form(""),
    warmth: WarmthLevel = Form(WarmthLevel.medium),
    name: str = Form(""),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Formato de imagen no soportado.")

    image_path = save_garment_image(image)
    garment = Garment(
        owner_id=current_user.id,
        name=name,
        category=category,
        color=color,
        warmth=warmth,
        image_path=image_path,
    )
    db.add(garment)
    db.commit()
    db.refresh(garment)
    return _to_out(garment)


@router.delete("/{garment_id}", status_code=204)
def delete_garment(garment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    garment = (
        db.query(Garment)
        .filter(Garment.id == garment_id, Garment.owner_id == current_user.id)
        .first()
    )
    if not garment:
        raise HTTPException(status_code=404, detail="Prenda no encontrada.")
    db.delete(garment)
    db.commit()
