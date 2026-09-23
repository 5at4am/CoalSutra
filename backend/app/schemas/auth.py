from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserRead(BaseModel):
    username: str
    role: str


class AuthConfigResponse(BaseModel):
    """Whether auth is enforced + which demo users exist (for the login hint)."""

    auth_enabled: bool
    demo_users: dict[str, str]