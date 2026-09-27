from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Table, Column, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

outfit_garments = Table(
    "outfit_garments",
    Base.metadata,
    Column("outfit_id", ForeignKey("outfits.id"), primary_key=True),
    Column("garment_id", ForeignKey("garments.id"), primary_key=True),
)


class Outfit(Base):
    __tablename__ = "outfits"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    occasion: Mapped[str] = mapped_column(String(60), nullable=False)
    weather_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    weather_condition: Mapped[str] = mapped_column(String(120), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner: Mapped["User"] = relationship(back_populates="outfits")
    garments: Mapped[list["Garment"]] = relationship(secondary=outfit_garments)
