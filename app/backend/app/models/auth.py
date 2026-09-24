from pydantic import BaseModel, ConfigDict
from datetime import datetime

class LoginRequest(BaseModel):
    login_id: str
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    login_id: str
    created_at: datetime
    is_active: bool

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str
