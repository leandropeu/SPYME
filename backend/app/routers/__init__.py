"""Router package exports with compatibility aliases for newer modules."""

from . import auth, backups, cameras, cloud_accounts, dashboard, dvrs, events, network_assets, units, users
from . import routers_audit as audit
from . import routers_dvr_remote as dvr_remote
from . import routers_streaming as streaming

__all__ = [
    "auth",
    "audit",
    "backups",
    "cameras",
    "cloud_accounts",
    "dashboard",
    "dvr_remote",
    "dvrs",
    "events",
    "network_assets",
    "streaming",
    "units",
    "users",
]
