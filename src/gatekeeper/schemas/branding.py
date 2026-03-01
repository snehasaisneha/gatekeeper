"""Branding schemas for API requests/responses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl

from gatekeeper.models.branding import ACCENT_PRESETS

# Type for accent color presets
AccentColor = Literal["ink", "charcoal", "navy", "forest", "amber", "plum", "sage"]


class BrandingRead(BaseModel):
    """Public branding settings response."""

    logo_url: str | None = None
    logo_square_url: str | None = None
    favicon_url: str | None = None
    accent_color: AccentColor = "ink"
    accent_hex: str = "#000000"

    model_config = {"from_attributes": True}


class BrandingUpdate(BaseModel):
    """Request to update branding settings."""

    logo_url: HttpUrl | None = None
    logo_square_url: HttpUrl | None = None
    favicon_url: HttpUrl | None = None
    accent_color: AccentColor | None = None


class BrandingReadAdmin(BrandingRead):
    """Admin branding response with metadata."""

    updated_at: datetime | None = None
    updated_by: str | None = None


class AccentPresetInfo(BaseModel):
    """Info about an accent color preset."""

    name: str
    hex: str


class AccentPresetsResponse(BaseModel):
    """List of available accent presets."""

    presets: list[AccentPresetInfo]

    @classmethod
    def from_presets(cls) -> "AccentPresetsResponse":
        return cls(
            presets=[
                AccentPresetInfo(name=name, hex=hex_color)
                for name, hex_color in ACCENT_PRESETS.items()
            ]
        )
