"""Navigation menu items for NetBox Vcenter plugin."""

from netbox.plugins import PluginMenuItem

menu_items = (
    PluginMenuItem(
        link="plugins:netbox_vcenter:settings",
        link_text="Vcenter Settings",
        permissions=["dcim.view_device"],
    ),
)
