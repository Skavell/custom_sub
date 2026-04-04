from pydantic import BaseModel


class SubscriptionLinkResponse(BaseModel):
    subscription_url: str


class OsAppConfigResponse(BaseModel):
    app_name: str
    store_url: str


class InstallAppConfigResponse(BaseModel):
    android: OsAppConfigResponse
    ios: OsAppConfigResponse
    windows: OsAppConfigResponse
    macos: OsAppConfigResponse
    linux: OsAppConfigResponse
