"""Views for NetBox Vcenter plugin."""

import logging

from dcim.models import Device
from django.shortcuts import render
from django.views.generic import View
from netbox.views.generic import ObjectView
from utilities.views import ViewTab, register_model_view
from virtualization.models import VirtualMachine

from .client import get_client

logger = logging.getLogger(__name__)


def should_show_tab(obj):
    """Determine if tab should be shown for this object."""
    # TODO: Add your logic here
    # Example: Only show for devices with serial numbers
    # if not obj.serial:
    #     return False
    return True


@register_model_view(Device, "vcenter", path="vcenter")
class DeviceVcenterView(ObjectView):
    """Vcenter tab view for Device detail pages."""

    queryset = Device.objects.all()
    template_name = "netbox_vcenter/device_tab.html"
    tab = ViewTab(
        label="Vcenter",
        weight=9100,
        permission="dcim.view_device",
        hide_if_empty=False,
        visible=should_show_tab,
    )

    def get(self, request, pk):
        device = self.get_object()

        # TODO: Fetch data from external service
        client = get_client()
        results = {}
        error = None

        if client:
            try:
                results = client.get_data(device.name)
            except Exception as e:
                logger.error(f"Error fetching data for {device.name}: {e}")
                error = str(e)
        else:
            error = "Plugin not configured"

        return render(
            request,
            self.template_name,
            {
                "object": device,
                "tab": self.tab,
                "results": results,
                "error": error,
            },
        )


@register_model_view(VirtualMachine, "vcenter", path="vcenter")
class VMVcenterView(ObjectView):
    """Vcenter tab view for Virtual Machine detail pages."""

    queryset = VirtualMachine.objects.all()
    template_name = "netbox_vcenter/vm_tab.html"
    tab = ViewTab(
        label="Vcenter",
        weight=9100,
        permission="virtualization.view_virtualmachine",
        hide_if_empty=False,
        visible=should_show_tab,
    )

    def get(self, request, pk):
        vm = self.get_object()

        client = get_client()
        results = {}
        error = None

        if client:
            try:
                results = client.get_data(vm.name)
            except Exception as e:
                logger.error(f"Error fetching data for {vm.name}: {e}")
                error = str(e)
        else:
            error = "Plugin not configured"

        return render(
            request,
            self.template_name,
            {
                "object": vm,
                "tab": self.tab,
                "results": results,
                "error": error,
            },
        )


class SettingsView(View):
    """Plugin settings page."""

    template_name = "netbox_vcenter/settings.html"

    def get(self, request):
        client = get_client()
        connection_status = None

        if client:
            # TODO: Test connection
            pass

        return render(
            request,
            self.template_name,
            {
                "configured": client is not None,
                "connection_status": connection_status,
            },
        )
