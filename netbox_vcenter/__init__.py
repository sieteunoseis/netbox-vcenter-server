"""
NetBox vCenter Plugin

Provides a dashboard for viewing and importing VMs from VMware vCenter servers.
Supports multiple vCenter servers with per-server caching and VM import to NetBox.
"""

from netbox.plugins import PluginConfig

__version__ = "0.7.0"


class VcenterConfig(PluginConfig):
    """Plugin configuration for NetBox vCenter integration."""

    name = "netbox_vcenter"
    verbose_name = "NetBox vCenter"
    description = "View and import VMs from VMware vCenter servers"
    version = __version__
    author = "Jeremy Worden"
    author_email = "jeremy.worden@gmail.com"
    base_url = "vcenter"
    min_version = "4.7.4"

    # Required settings - plugin won't load without these
    required_settings = []

    # Default configuration values
    default_settings = {
        # List of vCenter servers to choose from
        "vcenter_servers": [],
        # Optional saved credentials per server, keyed by hostname, to skip the
        # manual login form (e.g. for a non-MFA read-only service account):
        # "vcenter_credentials": {
        #     "vc-01.example.com": {"username": "svc-netbox@vsphere.local", "password": "..."},
        # }
        "vcenter_credentials": {},
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
        # Optional VRF name to scope IP address dedup/creation during import (must exist in NetBox, or leave empty)
        # Existing IPAM records are only reused within this VRF, and new IP addresses are created in it
        "default_vrf": "",
        # Optional default tenant slug applied to IP addresses created during import (must exist in NetBox)
        "default_tenant": "",
        # Platform mappings - auto-map vCenter guest OS to NetBox platform
        # Each mapping has a "pattern" (regex to match against guest OS) and "platform" (NetBox platform slug)
        # Mappings are evaluated in order; first match wins
        # Example:
        # "platform_mappings": [
        #     {"pattern": r"Microsoft Windows Server 2022", "platform": "windows-server-2022"},
        #     {"pattern": r"Microsoft Windows Server 2019", "platform": "windows-server-2019"},
        #     {"pattern": r"Microsoft Windows Server", "platform": "windows-server"},
        #     {"pattern": r"Microsoft Windows 1[01]", "platform": "windows-desktop"},
        #     {"pattern": r"Ubuntu", "platform": "ubuntu"},
        #     {"pattern": r"CentOS", "platform": "centos"},
        #     {"pattern": r"Red Hat", "platform": "rhel"},
        #     {"pattern": r"Debian", "platform": "debian"},
        #     {"pattern": r"VMware Photon", "platform": "photon"},
        # ]
        "platform_mappings": [],
        # Sync vCenter VM Notes into NetBox comments on existing VMs ("update existing"
        # import and "Sync All Differences"), overwriting comments when they differ.
        # Off by default so existing comments are never replaced. Notes are always
        # used as the comments of newly imported VMs.
        "sync_vm_notes": False,
        # Optional name of a VirtualMachine custom field to populate with the vCenter
        # guest OS (e.g. "Microsoft Windows Server 2022 (64-bit)") on import and sync.
        # The custom field must already exist in NetBox (type Text, object type
        # Virtual Machine). Leave empty to disable.
        "guest_os_custom_field": "",
    }


config = VcenterConfig
