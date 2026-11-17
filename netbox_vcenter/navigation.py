"""Navigation menu items for NetBox vCenter plugin."""

from django.conf import settings
from netbox.plugins import PluginMenu, PluginMenuItem

_menu = PluginMenu(
    label="vCenter",
    groups=(
        (
            "Virtual Machines",
            (
                PluginMenuItem(
                    link="plugins:netbox_vcenter:dashboard",
                    link_text="Import Dashboard",
                    permissions=["virtualization.view_virtualmachine"],
                ),
                PluginMenuItem(
                    link="plugins:netbox_vcenter:compare",
                    link_text="Compare with NetBox",
                    permissions=["virtualization.view_virtualmachine"],
                ),
            ),
        ),
    ),
    icon_class="mdi mdi-server",
)


# top_level_menu=False puts this plugin's items under the shared "Plugins" menu
# (grouped by plugin name) instead of its own top-level sidebar menu.
if settings.PLUGINS_CONFIG.get("netbox_vcenter", {}).get("top_level_menu", True):
    menu = _menu
else:
    menu_items = tuple(item for group in _menu.groups for item in group.items)
