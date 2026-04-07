from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserBase(BaseModel):
    full_name: str
    email: str
    role: str = "viewer"
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(UserBase):
    password: str | None = Field(default=None, min_length=8)


class UserOut(ORMModel, UserBase):
    id: int
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AuthSessionOut(BaseModel):
    token: str
    expires_at: datetime
    user: UserOut


class UnitBase(BaseModel):
    name: str
    code: str = Field(..., max_length=24)
    city: str | None = None
    state: str | None = None
    address: str | None = None
    manager_name: str | None = None
    manager_phone: str | None = None
    network_label: str | None = None
    vpn_type: str | None = None
    vpn_host: str | None = None
    vpn_port: int | None = None
    vpn_username: str | None = None
    vpn_network_cidr: str | None = None
    vpn_adapter_name: str | None = None
    notes: str | None = None
    is_active: bool = True


class UnitSecretFields(BaseModel):
    vpn_password: str | None = None
    vpn_psk: str | None = None


class UnitCreate(UnitBase, UnitSecretFields):
    pass


class UnitUpdate(UnitBase, UnitSecretFields):
    pass


class UnitOut(ORMModel, UnitBase):
    id: int
    dvr_count: int = 0
    camera_count: int = 0
    network_asset_count: int = 0
    online_dvrs: int = 0
    online_cameras: int = 0
    has_vpn_password: bool = False
    has_vpn_psk: bool = False
    created_at: datetime
    updated_at: datetime


# ── Cloud Accounts ────────────────────────────────────────────

class CloudAccountBase(BaseModel):
    name:   str
    vendor: str = "hikvision"          # "hikvision" | "intelbras"
    email:  str
    notes:  str | None = None


class CloudAccountCreate(CloudAccountBase):
    password: str                      # texto puro → criptografado no router


class CloudAccountUpdate(BaseModel):
    name:     str | None = None
    vendor:   str | None = None
    email:    str | None = None
    password: str | None = None        # None = não alterar a senha
    notes:    str | None = None


class CloudAccountSummary(BaseModel):
    """Versão compacta para embutir dentro de DVROut."""
    id:     int
    name:   str
    vendor: str
    email:  str


class CloudAccountOut(CloudAccountBase):
    id:           int
    has_password: bool = False
    dvr_count:    int  = 0
    created_at:   datetime
    updated_at:   datetime


# ── DVRs ──────────────────────────────────────────────────────

class DVRBase(BaseModel):
    unit_id: int
    name: str
    vendor: str = "hikvision"
    model: str | None = None
    serial_number: str | None = None
    host: str
    port: int = 80
    protocol: str = "http"
    username: str = "admin"
    channel_count: int = 8
    api_status_path: str | None = None
    device_info_path: str | None = None
    notes: str | None = None
    is_active: bool = True
    cloud_account_id: int | None = None
    device_serial: str | None = None


class DVRCreate(DVRBase):
    password: str | None = None


class DVRUpdate(DVRBase):
    password: str | None = None


class DVROut(ORMModel, DVRBase):
    id: int
    status: str
    last_seen: datetime | None = None
    last_checked: datetime | None = None
    last_latency_ms: float | None = None
    has_password: bool = False
    unit_name: str | None = None
    camera_count: int = 0
    cloud_account: CloudAccountSummary | None = None
    created_at: datetime
    updated_at: datetime


# ── Cameras ───────────────────────────────────────────────────

class CameraBase(BaseModel):
    unit_id: int
    dvr_id: int | None = None
    name: str
    vendor: str = "hikvision"
    model: str | None = None
    channel_number: int = 1
    location: str | None = None
    resolution: str | None = None
    snapshot_path: str | None = None
    snapshot_url: str | None = None
    stream_path: str | None = None
    stream_url: str | None = None
    notes: str | None = None
    is_active: bool = True


class CameraCreate(CameraBase):
    pass


class CameraUpdate(CameraBase):
    pass


class CameraOut(ORMModel, CameraBase):
    id: int
    status: str
    unit_name: str | None = None
    dvr_name: str | None = None
    last_seen: datetime | None = None
    last_checked: datetime | None = None
    snapshot_endpoint: str
    preview_ready: bool = False
    stream_reference: str | None = None
    created_at: datetime
    updated_at: datetime


class NetworkAssetBase(BaseModel):
    unit_id: int
    dvr_id: int | None = None
    name: str
    asset_type: str = "device"
    vendor: str | None = None
    model: str | None = None
    host: str
    port: int | None = None
    protocol: str = "https"
    username: str | None = None
    path: str | None = None
    mac_address: str | None = None
    local_network: str | None = None
    notes: str | None = None
    is_active: bool = True


class NetworkAssetCreate(NetworkAssetBase):
    password: str | None = None


class NetworkAssetUpdate(NetworkAssetBase):
    password: str | None = None


class NetworkAssetOut(ORMModel, NetworkAssetBase):
    id: int
    unit_name: str | None = None
    dvr_name: str | None = None
    has_password: bool = False
    connection_label: str | None = None
    connection_target: str | None = None
    created_at: datetime
    updated_at: datetime


class MonitoringEventOut(ORMModel):
    id: int
    unit_id: int | None = None
    dvr_id: int | None = None
    camera_id: int | None = None
    source_type: str
    event_type: str
    severity: str
    title: str
    message: str
    metadata_json: str | None = None
    started_at: datetime
    resolved_at: datetime | None = None
    duration_seconds: float | None = None
    is_resolved: bool


class BackupRecordOut(ORMModel):
    id: int
    file_name: str
    file_path: str
    file_size: int | None = None
    status: str
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    retained_until: datetime | None = None


class DashboardOverview(BaseModel):
    totals: dict[str, Any]
    critical_events: list[MonitoringEventOut]
    units: list[UnitOut]
    latest_backups: list[BackupRecordOut]
