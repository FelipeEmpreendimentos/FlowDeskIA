from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


WhatsAppConnectionMode = Literal["COEXISTENCE", "CLOUD_API"]


class WhatsAppConnectRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    waba_id: str = Field(min_length=1, max_length=100)
    phone_number_id: str = Field(min_length=1, max_length=100)
    business_id: str | None = Field(default=None, max_length=100)
    connection_mode: WhatsAppConnectionMode = "COEXISTENCE"


class WhatsAppIntegrationOut(BaseModel):
    connected: bool
    phone_number_id: str | None = None
    waba_id: str | None = None
    business_id: str | None = None
    display_phone_number: str | None = None
    verified_name: str | None = None
    quality_rating: str | None = None
    connection_mode: WhatsAppConnectionMode | None = None
    updated_at: datetime | None = None


class WhatsAppConnectionTestOut(BaseModel):
    ok: bool
    message: str
    display_phone_number: str | None = None
    verified_name: str | None = None
    quality_rating: str | None = None
