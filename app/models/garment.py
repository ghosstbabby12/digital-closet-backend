import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class GarmentCategory(str, enum.Enum):
    top = "top"
    bottom = "bottom"
    dress = "dress"
    outerwear = "outerwear"
    shoes = "shoes"
    accessory = "accessory"


class WarmthLevel(str, enum.Enum):
    light = "light"       # tela ligera, para calor
    medium = "medium"     # entretiempo
    heavy = "heavy"       # abrigo, para frío


class Garment(Base):
    __tablename__ = "garments"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(120), default="")
    category: Mapped[GarmentCategory] = mapped_column(Enum(GarmentCategory), nullable=False)
    color: Mapped[str] = mapped_column(String(60), default="")
    warmth: Mapped[WarmthLevel] = mapped_column(Enum(WarmthLevel), default=WarmthLevel.medium)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    owner: Mapped["User"] = relationship(back_populates="garments")
