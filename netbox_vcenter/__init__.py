"""
NetBox vCenter Plugin

Provides a dashboard for viewing and importing VMs from VMware vCenter servers.
Supports multiple vCenter servers with per-server caching and VM import to NetBox.
"""

from netbox.plugins import PluginConfig

__version__ = "0.1.0"


class VcenterConfig(PluginConfig):
    """Plugin configuration for NetBox vCenter integration."""

    name = "netbox_vcenter"
    verbose_name = "vCenter"
    description = "View and import VMs from VMware vCenter servers"
    version = __version__
    author = "sieteunoseis"
    author_email = "jeremy.worden@gmail.com"
    base_url = "vcenter"
    min_version = "4.0.0"

    # Required settings - plugin won't load without these
    required_settings = []

    # Default configuration values
    default_settings = {
        # List of vCenter servers to choose from
        "vcenter_servers": [],
        # Connection settings
        "timeout": 60,  # Connection timeout in seconds (longer for MFA)
        "verify_ssl": False,  # SSL verification (False for self-signed certs)
        # MFA/2FA settings
        "mfa_enabled": False,  # Whether to show MFA warning
        "mfa_label": "MFA",  # Short label: "Duo", "2FA", "MFA", etc.
        "mfa_message": "Check your authenticator after clicking Connect & Sync.",
        # Name matching for duplicate detection
        # Options: "exact" (case-insensitive full name), "hostname" (strip domain), "regex" (custom pattern)
        "name_match_mode": "exact",
        # Regex pattern to extract the match portion from VM name (used when name_match_mode is "regex")
        # Example: r"^([^.]+)" extracts hostname (same as "hostname" mode)
        # Example: r"^(\w+\d+)" extracts letters followed by numbers
        "name_match_pattern": r"^([^.]+)",
        # Import/sync settings
        # Whether to normalize VM names on import (strip domain, lowercase)
        # e.g., "WebServer01.example.com" -> "webserver01"
        "normalize_imported_name": True,
        # Tag slug to apply to imported/synced VMs (must exist in NetBox, or leave empty)
        "default_tag": "",
        # Optional default role slug for imported VMs (must exist in NetBox, or leave empty)
        "default_role": "",
        # Optional default platform slug for imported VMs (must exist in NetBox, or leave empty)
        "default_platform": "",
    }


config = VcenterConfig
