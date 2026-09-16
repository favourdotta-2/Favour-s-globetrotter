from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Preference = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=30)]
Username = Annotated[str, StringConstraints(
    strip_whitespace=True, to_lower=True, min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$"
)]


class UserCreate(BaseModel):
    username: Username
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=80)
    preferences: list[Preference] = Field(default_factory=list, max_length=20)


class LoginRequest(BaseModel):
    username: Username
    password: str = Field(min_length=1, max_length=128)


class PublicUser(BaseModel):
    id: str
    username: str
    full_name: str = ""
    preferences: list[str] = Field(default_factory=list)
    bio: str = ""
    home_city: str = ""
    created_at: str = ""
    avatar_url: str | None = None


class PublicAuthor(BaseModel):
    username: str
    full_name: str = ""
    avatar_url: str | None = None


class ReviewCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    rating: int = Field(ge=1, le=5, strict=True)
    comment: str = Field(min_length=1, max_length=2000)


class AppRatingCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    rating: int = Field(ge=1, le=5, strict=True)
    comment: str = Field(default="", max_length=1000)


class AuthResponse(BaseModel):
    token: str
    user: PublicUser


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    full_name: str = Field(default="", max_length=80)
    preferences: list[Preference] = Field(default_factory=list, max_length=20)
    bio: str = Field(default="", max_length=280)
    home_city: str = Field(default="", max_length=80)


class ItineraryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=2, max_length=100)
    destination_ids: list[str] = Field(min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    notes: str = Field(default="", max_length=500)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def empty_date(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_trip(self) -> Self:
        if len(set(self.destination_ids)) != len(self.destination_ids):
            raise ValueError("Select each destination only once")
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("Provide both travel dates or leave both empty")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("End date must be on or after start date")
        return self


class ChatMessageCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    text: str = Field(default="", max_length=500)
    sticker: Literal["hello", "adventure", "love-cameroon", "lets-go"] | None = None
    media_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        if not self.text and not self.sticker and not self.media_id:
            raise ValueError("Write a message or choose a sticker, photo, or video")
        if self.sticker and self.media_id:
            raise ValueError("Send one attachment per message")
        return self


class ChatMessage(BaseModel):
    id: str
    username: str
    text: str
    created_at: datetime
