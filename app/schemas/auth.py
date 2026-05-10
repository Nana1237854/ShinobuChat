from pydantic import BaseModel


class DeviceAuthorizeRequest(BaseModel):
    email: str
    password: str
    device_name: str
    device_type: str = "unknown"


class DeviceAuthorizeResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class DeviceTokenRequest(BaseModel):
    device_code: str


class DeviceTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
