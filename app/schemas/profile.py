import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 ()-]{6,24}$")


class BodyPhotoOut(BaseModel):
    image_url: str | None


class AvatarOut(BaseModel):
    avatar_url: str | None


class ProfileOut(BaseModel):
    id: int
    email: str
    name: str | None
    phone: str | None
    avatar_url: str | None
    created_at: datetime
    garment_count: int
    outfit_count: int
    look_count: int
    has_body_photo: bool


class ProfileUpdate(BaseModel):
    """Solo se cambian los campos enviados. Un nombre o teléfono vacío se borra.
    Cambiar el correo exige la contraseña actual."""

    name: str | None = Field(default=None, max_length=80)
    phone: str | None = None
    email: EmailStr | None = None
    current_password: str | None = None

    @field_validator("name", "phone")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())
        return value or None

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, value: str | None) -> str | None:
        if value is not None and not PHONE_PATTERN.match(value):
            raise ValueError("El teléfono solo puede tener números, espacios, guiones, paréntesis y un + inicial.")
        return value


class ProfileUpdateOut(ProfileOut):
    # El token va ligado al correo: si cambia, la app debe guardar este nuevo.
    access_token: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)
