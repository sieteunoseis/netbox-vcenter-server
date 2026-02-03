"""Navigation menu items for NetBox vCenter plugin."""

from netbox.plugins import PluginMenu, PluginMenuItem

menu = PluginMenu(
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
