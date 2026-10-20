"""Compatibilidad para los ejecutores que importan el bloqueo desde scripts."""

from pharma_validator_api.maintenance_lock import (
    MaintenanceAlreadyRunning,
    maintenance_lock,
)

__all__ = ["MaintenanceAlreadyRunning", "maintenance_lock"]
