from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.garment import Garment
from app.models.look import Look
from app.models.outfit import Outfit
from app.models.user import User
from app.schemas.profile import BodyPhotoOut, ProfileOut
from app.services.background_removal import remove_background
from app.services.storage import body_photo_url, delete_body_photo, save_body_photo

router = APIRouter(prefix="/me", tags=["profile"])

MAX_PHOTO_BYTES = 12 * 1024 * 1024


@router.get("", response_model=ProfileOut)
def read_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    def count(model) -> int:
        return db.scalar(select(func.count()).select_from(model).where(model.owner_id == current_user.id))

    return ProfileOut(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
        garment_count=count(Garment),
        outfit_count=count(Outfit),
        look_count=count(Look),
        has_body_photo=current_user.body_photo_path is not None,
    )


@router.get("/body-photo", response_model=BodyPhotoOut)
def read_body_photo(current_user: User = Depends(get_current_user)):
    if not current_user.body_photo_path:
        return BodyPhotoOut(image_url=None)
    return BodyPhotoOut(image_url=body_photo_url(current_user.body_photo_path))


@router.put("/body-photo", response_model=BodyPhotoOut)
def upload_body_photo(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Formato de imagen no soportado.")
    content = image.file.read()
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="La foto es demasiado grande (máximo 12 MB).")

    # La foto original no se guarda: solo el recorte con fondo transparente.
    filename = save_body_photo(remove_background(content, image.content_type))
    previous = current_user.body_photo_path
    current_user.body_photo_path = filename
    db.commit()
    if previous:
        delete_body_photo(previous)
    return BodyPhotoOut(image_url=body_photo_url(filename))


@router.delete("/body-photo", status_code=204)
def remove_body_photo(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.body_photo_path:
        delete_body_photo(current_user.body_photo_path)
        current_user.body_photo_path = None
        db.commit()
