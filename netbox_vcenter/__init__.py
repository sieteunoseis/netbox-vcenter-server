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
        "vcenter_servers": [
            "vc-msb.ohsu.edu",
            "vc-dcw.ohsu.edu",
        ],
        # Connection settings
        "timeout": 60,  # Connection timeout in seconds (longer for MFA)
        "verify_ssl": False,  # SSL verification (False for self-signed certs)
        # MFA/2FA settings
        "mfa_enabled": True,  # Whether to show MFA warning
        "mfa_label": "2FA",  # Short label: "Duo", "2FA", "MFA", etc.
        "mfa_message": "After clicking \"Connect & Sync\", check your device for an authentication prompt.",
    }


config = VcenterConfig
