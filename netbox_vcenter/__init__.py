"""
NetBox Vcenter Plugin

TODO: Add plugin description here.
"""

from netbox.plugins import PluginConfig

__version__ = "0.1.0"


class VcenterConfig(PluginConfig):
    """Plugin configuration for NetBox Vcenter integration."""

    name = "netbox_vcenter"
    verbose_name = "Vcenter"
    description = "TODO: Add description"
    version = __version__
    author = "sieteunoseis"
    author_email = "jeremy.worden@gmail.com"
    base_url = "vcenter"
    min_version = "4.0.0"

    # Required settings - plugin won't load without these
    required_settings = []

    # Default configuration values
    default_settings = {
        # TODO: Add your plugin settings here
        # Example:
        # "api_url": "",
        # "api_token": "",
        "timeout": 30,
        "cache_timeout": 300,
        "verify_ssl": True,
    }


config = VcenterConfig
