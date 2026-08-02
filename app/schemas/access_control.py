from pydantic import BaseModel

from app.models.enums import CargoUsuario


class ModuleAccessOut(BaseModel):
    code: str
    name: str
    description: str
    enabled: bool
    allowed: bool
    default_allowed: bool


class CurrentAccessOut(BaseModel):
    modules: dict[str, bool]


class CompanyModuleOut(BaseModel):
    code: str
    name: str
    description: str
    enabled: bool


class CompanyModuleUpdate(BaseModel):
    enabled: bool


class UserModulePermissionsOut(BaseModel):
    user_id: int
    name: str
    email: str
    role: CargoUsuario
    active: bool
    permissions: dict[str, bool]
    overrides: dict[str, bool]


class UserModulePermissionUpdate(BaseModel):
    allowed: bool | None


class AccessConfigurationOut(BaseModel):
    modules: list[CompanyModuleOut]
    users: list[UserModulePermissionsOut]
