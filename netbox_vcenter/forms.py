"""Forms for NetBox vCenter plugin."""

from django import forms
from django.conf import settings
from virtualization.models import Cluster


class VCenterConnectForm(forms.Form):
    """Form for connecting to a vCenter server."""

    server = forms.ChoiceField(
        label="vCenter Server",
        help_text="Select the vCenter server to connect to",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    username = forms.CharField(
        label="Username",
        help_text="Enter your username (e.g., domain\\user or user@domain)",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "domain\\username"}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    verify_ssl = forms.BooleanField(
        label="Verify SSL Certificate",
        required=False,
        initial=False,
        help_text="Enable for trusted certificates (disable for self-signed)",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate server choices from plugin config
        config = settings.PLUGINS_CONFIG.get("netbox_vcenter", {})
        servers = config.get("vcenter_servers", [])
        self.fields["server"].choices = [(s, s) for s in servers]


class VMImportForm(forms.Form):
    """Form for importing VMs from vCenter to NetBox."""

    cluster = forms.ModelChoiceField(
        queryset=Cluster.objects.all(),
        label="Target Cluster",
        help_text="NetBox cluster to assign the imported VMs to",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    selected_vms = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="JSON list of selected VM names",
    )
    vcenter_server = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="Source vCenter server",
    )
    update_existing = forms.BooleanField(
        label="Update existing VMs",
        required=False,
        initial=False,
        help_text="Update vCPUs, memory, disk, status, and IP address for VMs that already exist in NetBox",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_selected_vms(self):
        """Parse the selected VMs JSON string."""
        import json

        data = self.cleaned_data.get("selected_vms", "[]")
        try:
            vms = json.loads(data)
            if not isinstance(vms, list):
                raise forms.ValidationError("Invalid VM selection format")
            return vms
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid VM selection data")
