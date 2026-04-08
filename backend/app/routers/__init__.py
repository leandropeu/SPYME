"""Router package exports with compatibility aliases for newer modules."""

from . import auth, backups, cameras, cloud_accounts, dvrs, events, units, users
from . import routers_dvr_remote as dvr_remote
from . import routers_streaming as streaming

__all__ = [
    "auth",
    "backups",
    "cameras",
    "cloud_accounts",
    "dvr_remote",
    "dvrs",
    "events",
    "streaming",
    "units",
    "users",
]
