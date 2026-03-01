"""Branding model for whitelabeling settings."""

from datetime import datetime

from sqlalchemy import CheckConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from gatekeeper.database import Base

# Available accent color presets
ACCENT_PRESETS = {
    "ink": "#000000",
    "charcoal": "#374151",
    "navy": "#1e3a5f",
    "forest": "#1a4d2e",
    "amber": "#b45309",
    "plum": "#5c3d5e",
    "sage": "#4d6a5a",
}


class Branding(Base):
    """Branding settings for whitelabeling.

    This is a single-row table enforced by a CHECK constraint.
    """

    __tablename__ = "branding"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # Logo URLs (all optional - graceful fallbacks to text)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_square_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Accent color (preset name from ACCENT_PRESETS)
    accent_color: Mapped[str] = mapped_column(Text, nullable=False, default="ink")

    # Metadata
    updated_at: Mapped[datetime] = mapped_column(Text, nullable=False, default=datetime.utcnow)
    updated_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def accent_hex(self) -> str:
        """Get the hex color for the current accent preset."""
        return ACCENT_PRESETS.get(self.accent_color, ACCENT_PRESETS["ink"])
