from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.garment import Garment
from app.models.look import Look
from app.models.outfit import Outfit
from app.models.user import User
from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.profile import (
    AvatarOut,
    BodyPhotoOut,
    PasswordChange,
    ProfileOut,
    ProfileUpdate,
    ProfileUpdateOut,
)
from app.services.background_removal import remove_background
from app.services.storage import (
    avatar_url,
    body_photo_url,
    delete_avatar,
    delete_body_photo,
    save_avatar,
    save_body_photo,
)

router = APIRouter(prefix="/me", tags=["profile"])

MAX_PHOTO_BYTES = 12 * 1024 * 1024
MAX_AVATAR_BYTES = 5 * 1024 * 1024
AVATAR_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _profile(db: Session, user: User) -> ProfileOut:
    def count(model) -> int:
        return db.scalar(select(func.count()).select_from(model).where(model.owner_id == user.id))

    return ProfileOut(
        id=user.id,
        email=user.email,
        name=user.name,
        phone=user.phone,
        avatar_url=avatar_url(user.avatar_path) if user.avatar_path else None,
        created_at=user.created_at,
        garment_count=count(Garment),
        outfit_count=count(Outfit),
        look_count=count(Look),
        has_body_photo=user.body_photo_path is not None,
    )


def _check_password(user: User, password: str | None) -> None:
    if not password or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")


@router.get("", response_model=ProfileOut)
def read_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _profile(db, current_user)


@router.patch("", response_model=ProfileUpdateOut)
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sent = payload.model_fields_set
    if "email" in sent and payload.email is None:
        raise HTTPException(status_code=422, detail="El correo no puede quedar vacío.")
    if payload.email is not None and payload.email != current_user.email:
        _check_password(current_user, payload.current_password)
        taken = db.query(User).filter(User.email == payload.email, User.id != current_user.id).first()
        if taken:
            raise HTTPException(status_code=400, detail="Ya existe una cuenta con ese correo.")
        current_user.email = payload.email
    if "name" in sent:
        current_user.name = payload.name
    if "phone" in sent:
        current_user.phone = payload.phone
    db.commit()
    db.refresh(current_user)
    return ProfileUpdateOut(
        **_profile(db, current_user).model_dump(),
        access_token=create_access_token(subject=current_user.email),
    )


@router.put("/password", status_code=204)
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_password(current_user, payload.current_password)
    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()


@router.put("/avatar", response_model=AvatarOut)
def upload_avatar(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    extension = AVATAR_EXTENSIONS.get(image.content_type or "")
    if extension is None:
        raise HTTPException(status_code=400, detail="Formato de imagen no soportado.")
    content = image.file.read()
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="La foto es demasiado grande (máximo 5 MB).")

    filename = save_avatar(content, extension, image.content_type)
    previous = current_user.avatar_path
    current_user.avatar_path = filename
    db.commit()
    if previous:
        delete_avatar(previous)
    return AvatarOut(avatar_url=avatar_url(filename))


@router.delete("/avatar", status_code=204)
def remove_avatar(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.avatar_path:
        delete_avatar(current_user.avatar_path)
        current_user.avatar_path = None
        db.commit()


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
