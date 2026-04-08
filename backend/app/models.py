from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    tokens: Mapped[list["AuthToken"]] = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    user: Mapped["User"] = relationship("User", back_populates="tokens")


class Unit(TimestampMixin, Base):
    __tablename__ = "units"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, index=True)
    city: Mapped[str | None] = mapped_column(String(80))
    state: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(String(255))
    manager_name: Mapped[str | None] = mapped_column(String(120))
    manager_phone: Mapped[str | None] = mapped_column(String(40))
    network_label: Mapped[str | None] = mapped_column(String(120))
    vpn_type: Mapped[str | None] = mapped_column(String(40))
    vpn_host: Mapped[str | None] = mapped_column(String(120))
    vpn_port: Mapped[int | None] = mapped_column(Integer)
    vpn_username: Mapped[str | None] = mapped_column(String(120))
    vpn_password_encrypted: Mapped[str | None] = mapped_column(Text)
    vpn_psk_encrypted: Mapped[str | None] = mapped_column(Text)
    vpn_network_cidr: Mapped[str | None] = mapped_column(String(64))
    vpn_adapter_name: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    dvrs: Mapped[list["DVR"]] = relationship("DVR", back_populates="unit", cascade="all, delete-orphan")
    cameras: Mapped[list["Camera"]] = relationship("Camera", back_populates="unit", cascade="all, delete-orphan")
    network_assets: Mapped[list["NetworkAsset"]] = relationship("NetworkAsset", back_populates="unit", cascade="all, delete-orphan")


class CloudAccount(TimestampMixin, Base):
    __tablename__ = "cloud_accounts"
    id:           Mapped[int]      = mapped_column(Integer, primary_key=True, index=True)
    name:         Mapped[str]      = mapped_column(String(120), nullable=False)
    vendor:       Mapped[str]      = mapped_column(String(40),  nullable=False)
    email:        Mapped[str]      = mapped_column(String(160), nullable=False)
    password_enc: Mapped[str]      = mapped_column(Text,        nullable=False)
    notes:        Mapped[str|None] = mapped_column(Text)
    dvrs: Mapped[list["DVR"]] = relationship("DVR", back_populates="cloud_account", lazy="select")


class DVR(TimestampMixin, Base):
    __tablename__ = "dvrs"
    __table_args__ = (UniqueConstraint("unit_id", "name", name="uq_dvr_unit_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    vendor: Mapped[str] = mapped_column(String(40), default="hikvision")
    model: Mapped[str | None] = mapped_column(String(120))
    serial_number: Mapped[str | None] = mapped_column(String(120))
    host: Mapped[str] = mapped_column(String(120), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=80)
    protocol: Mapped[str] = mapped_column(String(8), default="http")
    username: Mapped[str] = mapped_column(String(80), default="admin")
    password_encrypted: Mapped[str | None] = mapped_column(Text)
    owner_username: Mapped[str | None] = mapped_column(String(80))
    owner_password_encrypted: Mapped[str | None] = mapped_column(Text)
    channel_count: Mapped[int] = mapped_column(Integer, default=8)
    api_status_path: Mapped[str | None] = mapped_column(String(255))
    device_info_path: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime)
    last_latency_ms: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    cloud_account_id: Mapped[int | None] = mapped_column(ForeignKey("cloud_accounts.id", ondelete="SET NULL"), index=True)
    device_serial: Mapped[str | None] = mapped_column(String(120))
    unit: Mapped["Unit"] = relationship("Unit", back_populates="dvrs")
    cameras: Mapped[list["Camera"]] = relationship("Camera", back_populates="dvr", cascade="all, delete-orphan")
    events: Mapped[list["MonitoringEvent"]] = relationship("MonitoringEvent", back_populates="dvr", foreign_keys="MonitoringEvent.dvr_id")
    cloud_account: Mapped["CloudAccount | None"] = relationship("CloudAccount", back_populates="dvrs")


class Camera(TimestampMixin, Base):
    __tablename__ = "cameras"
    __table_args__ = (UniqueConstraint("dvr_id", "channel_number", name="uq_camera_channel_per_dvr"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True)
    dvr_id: Mapped[int | None] = mapped_column(ForeignKey("dvrs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    vendor: Mapped[str] = mapped_column(String(40), default="hikvision")
    model: Mapped[str | None] = mapped_column(String(120))
    channel_number: Mapped[int] = mapped_column(Integer, default=1)
    location: Mapped[str | None] = mapped_column(String(120))
    resolution: Mapped[str | None] = mapped_column(String(40))
    snapshot_path: Mapped[str | None] = mapped_column(String(255))
    snapshot_url: Mapped[str | None] = mapped_column(String(500))
    stream_path: Mapped[str | None] = mapped_column(String(255))
    stream_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    unit: Mapped["Unit"] = relationship("Unit", back_populates="cameras")
    dvr: Mapped["DVR | None"] = relationship("DVR", back_populates="cameras")
    events: Mapped[list["MonitoringEvent"]] = relationship("MonitoringEvent", back_populates="camera", foreign_keys="MonitoringEvent.camera_id")


class NetworkAsset(TimestampMixin, Base):
    __tablename__ = "network_assets"
    __table_args__ = (UniqueConstraint("unit_id", "name", name="uq_network_asset_unit_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True)
    dvr_id: Mapped[int | None] = mapped_column(ForeignKey("dvrs.id", ondelete="SET NULL"), index=True)
    parent_asset_id: Mapped[int | None] = mapped_column(ForeignKey("network_assets.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(40), default="device")
    vendor: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(120))
    host: Mapped[str] = mapped_column(String(120), nullable=False)
    port: Mapped[int | None] = mapped_column(Integer)
    protocol: Mapped[str] = mapped_column(String(20), default="https")
    username: Mapped[str | None] = mapped_column(String(120))
    password_encrypted: Mapped[str | None] = mapped_column(Text)
    path: Mapped[str | None] = mapped_column(String(255))
    mac_address: Mapped[str | None] = mapped_column(String(32))
    local_network: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime)
    last_latency_ms: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    unit: Mapped["Unit"] = relationship("Unit", back_populates="network_assets")
    dvr: Mapped["DVR | None"] = relationship("DVR")
    parent_asset: Mapped["NetworkAsset | None"] = relationship("NetworkAsset", remote_side=[id], back_populates="children")
    children: Mapped[list["NetworkAsset"]] = relationship("NetworkAsset", back_populates="parent_asset")
    events: Mapped[list["MonitoringEvent"]] = relationship("MonitoringEvent", back_populates="network_asset", foreign_keys="MonitoringEvent.network_asset_id")


class MonitoringEvent(Base):
    __tablename__ = "monitoring_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id", ondelete="SET NULL"), index=True)
    dvr_id: Mapped[int | None] = mapped_column(ForeignKey("dvrs.id", ondelete="SET NULL"), index=True)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), index=True)
    network_asset_id: Mapped[int | None] = mapped_column(ForeignKey("network_assets.id", ondelete="SET NULL"), index=True)
    source_type: Mapped[str] = mapped_column(String(20), default="dvr")
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="warning")
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    dvr: Mapped["DVR | None"] = relationship("DVR", back_populates="events", foreign_keys=[dvr_id])
    camera: Mapped["Camera | None"] = relationship("Camera", back_populates="events", foreign_keys=[camera_id])
    network_asset: Mapped["NetworkAsset | None"] = relationship("NetworkAsset", back_populates="events", foreign_keys=[network_asset_id])


class BackupRecord(Base):
    __tablename__ = "backup_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    retained_until: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(Base):
    """Registro imutável de toda ação realizada no sistema."""
    __tablename__ = "audit_logs"
    id:          Mapped[int]      = mapped_column(Integer, primary_key=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    action:      Mapped[str]      = mapped_column(String(40),  nullable=False, index=True)
    entity:      Mapped[str]      = mapped_column(String(40),  nullable=False, index=True)
    entity_id:   Mapped[str|None] = mapped_column(String(40))
    user_id:     Mapped[int|None] = mapped_column(Integer, index=True)
    user_email:  Mapped[str|None] = mapped_column(String(160))
    detail:      Mapped[str|None] = mapped_column(Text)
    before_json: Mapped[str|None] = mapped_column(Text)
    after_json:  Mapped[str|None] = mapped_column(Text)
