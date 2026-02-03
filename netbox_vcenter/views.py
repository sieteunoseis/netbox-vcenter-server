"""Views for NetBox vCenter plugin."""

import json
import logging
import re

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import View
from virtualization.models import Cluster, VirtualMachine

from .client import connect_and_fetch
from .forms import VCenterConnectForm, VMImportForm

logger = logging.getLogger(__name__)


def normalize_name(name: str, mode: str = "exact", pattern: str = None) -> str:
    """
    Normalize a VM name for matching based on the configured mode.

    Args:
        name: The VM name to normalize
        mode: Match mode - "exact", "hostname", or "regex"
        pattern: Regex pattern (used when mode is "regex")

    Returns:
        Normalized name for comparison (always lowercase)
    """
    if not name:
        return ""

    name = name.strip()

    if mode == "hostname":
        # Strip domain - everything after first dot
        name = name.split(".")[0]
    elif mode == "regex" and pattern:
        try:
            match = re.match(pattern, name, re.IGNORECASE)
            if match and match.groups():
                name = match.group(1)
        except re.error:
            logger.warning(f"Invalid regex pattern: {pattern}")

    return name.lower()


def get_name_match_config() -> tuple[str, str]:
    """Get the name matching configuration."""
    config = settings.PLUGINS_CONFIG.get("netbox_vcenter", {})
    mode = config.get("name_match_mode", "exact")
    pattern = config.get("name_match_pattern", r"^([^.]+)")
    return mode, pattern


def build_netbox_name_map(mode: str, pattern: str) -> dict[str, str]:
    """
    Build a mapping of normalized names to original NetBox VM names.

    Returns:
        Dict mapping normalized_name -> original_name
    """
    name_map = {}
    for name in VirtualMachine.objects.values_list("name", flat=True):
        normalized = normalize_name(name, mode, pattern)
        if normalized not in name_map:
            name_map[normalized] = name
    return name_map


def check_vm_exists(vm_name: str, mode: str, pattern: str, netbox_names: set) -> bool:
    """Check if a VM exists in NetBox using the configured matching mode."""
    normalized = normalize_name(vm_name, mode, pattern)
    return normalized in netbox_names


def get_cache_key(server: str) -> str:
    """Generate cache key for a vCenter server."""
    return f"vcenter_vms_{server.replace('.', '_')}"


def get_cached_data(server: str) -> dict:
    """Get cached VM data for a vCenter server."""
    return cache.get(get_cache_key(server))


def get_all_cached_data() -> dict:
    """Get cached data for all configured vCenter servers."""
    config = settings.PLUGINS_CONFIG.get("netbox_vcenter", {})
    servers = config.get("vcenter_servers", [])

    cached_data = {}
    for server in servers:
        data = get_cached_data(server)
        cached_data[server] = data

    return cached_data


class VCenterDashboardView(View):
    """Main dashboard for viewing and syncing vCenter VMs."""

    template_name = "netbox_vcenter/dashboard.html"

    def get(self, request):
        """Display the dashboard with connection form and cached VMs."""
        form = VCenterConnectForm()
        cached_data = get_all_cached_data()

        # Get the selected server tab (default to first server with data, or first server)
        config = settings.PLUGINS_CONFIG.get("netbox_vcenter", {})
        servers = config.get("vcenter_servers", [])
        selected_server = request.GET.get("server")

        if not selected_server:
            # Default to first server with cached data, or first server
            for server in servers:
                if cached_data.get(server):
                    selected_server = server
                    break
            if not selected_server and servers:
                selected_server = servers[0]

        # Get VMs for selected server
        selected_data = cached_data.get(selected_server) if selected_server else None
        vms = selected_data.get("vms", []) if selected_data else []

        # Sort VMs by name
        vms = sorted(vms, key=lambda x: x.get("name", "").lower())

        # Get name matching config and check which VMs already exist in NetBox
        match_mode, match_pattern = get_name_match_config()
        existing_normalized = {
            normalize_name(name, match_mode, match_pattern)
            for name in VirtualMachine.objects.values_list("name", flat=True)
        }
        for vm in vms:
            vm_normalized = normalize_name(vm.get("name", ""), match_mode, match_pattern)
            vm["exists_in_netbox"] = vm_normalized in existing_normalized

        # Get MFA settings
        mfa_enabled = config.get("mfa_enabled", True)
        mfa_label = config.get("mfa_label", "2FA")
        mfa_message = config.get("mfa_message", "Check your device for an authentication prompt.")

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "servers": servers,
                "cached_data": cached_data,
                "selected_server": selected_server,
                "vms": vms,
                "vm_count": len(vms),
                "mfa_enabled": mfa_enabled,
                "mfa_label": mfa_label,
                "mfa_message": mfa_message,
            },
        )

    def post(self, request):
        """Connect to vCenter and fetch VMs."""
        form = VCenterConnectForm(request.POST)

        if form.is_valid():
            server = form.cleaned_data["server"]
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            verify_ssl = form.cleaned_data.get("verify_ssl", False)

            # Connect and fetch VMs
            vms, error = connect_and_fetch(server, username, password, verify_ssl)

            if error:
                messages.error(request, error)
            else:
                # Cache the data (no timeout - persists until manual refresh)
                cache_data = {
                    "vms": vms,
                    "timestamp": timezone.now().isoformat(),
                    "server": server,
                    "count": len(vms),
                }
                cache.set(get_cache_key(server), cache_data, None)
                messages.success(request, f"Successfully synced {len(vms)} VMs from {server}")

            return redirect(f"{request.path}?server={server}")

        # Form invalid
        cached_data = get_all_cached_data()
        config = settings.PLUGINS_CONFIG.get("netbox_vcenter", {})
        servers = config.get("vcenter_servers", [])

        # Get MFA settings
        mfa_enabled = config.get("mfa_enabled", True)
        mfa_label = config.get("mfa_label", "2FA")
        mfa_message = config.get("mfa_message", "Check your device for an authentication prompt.")

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "servers": servers,
                "cached_data": cached_data,
                "selected_server": servers[0] if servers else None,
                "vms": [],
                "vm_count": 0,
                "mfa_enabled": mfa_enabled,
                "mfa_label": mfa_label,
                "mfa_message": mfa_message,
            },
        )


class VCenterRefreshView(View):
    """Clear cached data for a vCenter server."""

    def get(self, request, server):
        """Clear cache and redirect to dashboard."""
        cache.delete(get_cache_key(server))
        messages.info(request, f"Cache cleared for {server}. Enter credentials to sync again.")
        return redirect(f"/plugins/vcenter/?server={server}")


class VMImportView(View):
    """Import selected VMs from vCenter to NetBox."""

    template_name = "netbox_vcenter/import.html"

    def get(self, request):
        """Show import preview/confirmation page."""
        selected_vms_json = request.GET.get("vms", "[]")
        server = request.GET.get("server", "")

        try:
            selected_vm_names = json.loads(selected_vms_json)
        except json.JSONDecodeError:
            selected_vm_names = []

        if not selected_vm_names:
            messages.warning(request, "No VMs selected for import")
            return redirect("plugins:netbox_vcenter:dashboard")

        # Get VM details from cache
        cached_data = get_cached_data(server)
        if not cached_data:
            messages.error(request, f"No cached data for {server}. Please sync first.")
            return redirect("plugins:netbox_vcenter:dashboard")

        # Filter to selected VMs
        all_vms = cached_data.get("vms", [])
        vms_to_import = [vm for vm in all_vms if vm.get("name") in selected_vm_names]

        # Get name matching config and check which VMs already exist in NetBox
        match_mode, match_pattern = get_name_match_config()
        existing_normalized = {
            normalize_name(name, match_mode, match_pattern)
            for name in VirtualMachine.objects.values_list("name", flat=True)
        }
        for vm in vms_to_import:
            vm_normalized = normalize_name(vm.get("name", ""), match_mode, match_pattern)
            vm["exists_in_netbox"] = vm_normalized in existing_normalized

        form = VMImportForm(
            initial={
                "selected_vms": json.dumps(selected_vm_names),
                "vcenter_server": server,
            }
        )

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "vms": vms_to_import,
                "server": server,
                "new_count": len([v for v in vms_to_import if not v.get("exists_in_netbox")]),
                "existing_count": len([v for v in vms_to_import if v.get("exists_in_netbox")]),
            },
        )

    def post(self, request):
        """Import the selected VMs to NetBox."""
        form = VMImportForm(request.POST)

        if not form.is_valid():
            messages.error(request, "Invalid form data")
            return redirect("plugins:netbox_vcenter:dashboard")

        selected_vm_names = form.cleaned_data["selected_vms"]
        server = form.cleaned_data["vcenter_server"]
        cluster = form.cleaned_data["cluster"]

        # Get VM details from cache
        cached_data = get_cached_data(server)
        if not cached_data:
            messages.error(request, f"No cached data for {server}. Please sync first.")
            return redirect("plugins:netbox_vcenter:dashboard")

        # Filter to selected VMs
        all_vms = cached_data.get("vms", [])
        vms_to_import = [vm for vm in all_vms if vm.get("name") in selected_vm_names]

        # Get name matching config for duplicate detection
        match_mode, match_pattern = get_name_match_config()
        existing_normalized = {
            normalize_name(name, match_mode, match_pattern)
            for name in VirtualMachine.objects.values_list("name", flat=True)
        }

        # Import VMs
        created = 0
        skipped = 0
        errors = []

        for vm_data in vms_to_import:
            vm_name = vm_data.get("name")

            # Check if VM already exists using configured matching
            vm_normalized = normalize_name(vm_name, match_mode, match_pattern)
            if vm_normalized in existing_normalized:
                skipped += 1
                continue

            try:
                # Determine status based on power state
                status = "active" if vm_data.get("power_state") == "on" else "offline"

                # Create the VM
                vm = VirtualMachine(
                    name=vm_name,
                    cluster=cluster,
                    vcpus=vm_data.get("vcpus"),
                    memory=vm_data.get("memory_mb"),
                    disk=vm_data.get("disk_gb"),
                    status=status,
                    comments=f"Imported from vCenter {server} on {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                )
                vm.full_clean()
                vm.save()
                created += 1

            except Exception as e:
                errors.append(f"{vm_name}: {str(e)}")
                logger.error(f"Error importing VM {vm_name}: {e}")

        # Build result message
        if created:
            messages.success(request, f"Successfully imported {created} VM(s) to cluster '{cluster.name}'")
        if skipped:
            messages.info(request, f"Skipped {skipped} VM(s) that already exist in NetBox")
        if errors:
            messages.warning(request, f"Failed to import {len(errors)} VM(s): {'; '.join(errors[:3])}")

        return redirect("plugins:netbox_vcenter:dashboard")


class VMComparisonView(View):
    """Compare vCenter VMs with NetBox VMs."""

    template_name = "netbox_vcenter/compare.html"

    def get(self, request):
        """Show comparison between vCenter and NetBox VMs."""
        server = request.GET.get("server", "")

        # Get name matching config
        match_mode, match_pattern = get_name_match_config()

        # Get vCenter VMs from cache
        cached_data = get_cached_data(server) if server else None
        vcenter_vms = cached_data.get("vms", []) if cached_data else []

        # Build maps: normalized_name -> original data
        vcenter_normalized_map = {}  # normalized -> vm_data
        for vm in vcenter_vms:
            name = vm.get("name", "")
            normalized = normalize_name(name, match_mode, match_pattern)
            vcenter_normalized_map[normalized] = vm

        # Get NetBox VMs
        netbox_vms = VirtualMachine.objects.all()
        netbox_normalized_map = {}  # normalized -> vm_object
        for vm in netbox_vms:
            normalized = normalize_name(vm.name, match_mode, match_pattern)
            netbox_normalized_map[normalized] = vm

        vcenter_normalized = set(vcenter_normalized_map.keys())
        netbox_normalized = set(netbox_normalized_map.keys())

        # Categorize VMs by normalized names
        in_both = vcenter_normalized & netbox_normalized
        only_in_vcenter = vcenter_normalized - netbox_normalized
        only_in_netbox = netbox_normalized - vcenter_normalized

        # Build comparison lists
        comparison = {
            "in_both": [],
            "only_in_vcenter": [],
            "only_in_netbox": [],
        }

        # VMs in both - check for spec differences
        for normalized in sorted(in_both):
            vc_vm = vcenter_normalized_map.get(normalized, {})
            nb_vm = netbox_normalized_map.get(normalized)

            diff = {
                "name": vc_vm.get("name", normalized),  # Show original vCenter name
                "netbox_name": nb_vm.name if nb_vm else None,  # Show NetBox name if different
                "vcenter": vc_vm,
                "netbox": {
                    "vcpus": nb_vm.vcpus if nb_vm else None,
                    "memory_mb": nb_vm.memory if nb_vm else None,
                    "disk_gb": nb_vm.disk if nb_vm else None,
                    "status": nb_vm.status if nb_vm else None,
                },
                "has_differences": False,
            }

            # Check for differences
            if vc_vm.get("vcpus") != diff["netbox"]["vcpus"]:
                diff["has_differences"] = True
            if vc_vm.get("memory_mb") != diff["netbox"]["memory_mb"]:
                diff["has_differences"] = True
            if vc_vm.get("disk_gb") != diff["netbox"]["disk_gb"]:
                diff["has_differences"] = True

            comparison["in_both"].append(diff)

        # VMs only in vCenter
        for normalized in sorted(only_in_vcenter):
            vc_vm = vcenter_normalized_map.get(normalized, {})
            comparison["only_in_vcenter"].append(vc_vm if vc_vm else {"name": normalized})

        # VMs only in NetBox
        for normalized in sorted(only_in_netbox):
            nb_vm = netbox_normalized_map.get(normalized)
            comparison["only_in_netbox"].append(
                {
                    "name": nb_vm.name if nb_vm else normalized,
                    "vcpus": nb_vm.vcpus if nb_vm else None,
                    "memory_mb": nb_vm.memory if nb_vm else None,
                    "cluster": nb_vm.cluster.name if nb_vm and nb_vm.cluster else None,
                }
            )

        # Get all servers for selector
        config = settings.PLUGINS_CONFIG.get("netbox_vcenter", {})
        servers = config.get("vcenter_servers", [])

        return render(
            request,
            self.template_name,
            {
                "server": server,
                "servers": servers,
                "cached_data": cached_data,
                "comparison": comparison,
                "in_both_count": len(comparison["in_both"]),
                "only_vcenter_count": len(comparison["only_in_vcenter"]),
                "only_netbox_count": len(comparison["only_in_netbox"]),
                "diff_count": len([c for c in comparison["in_both"] if c.get("has_differences")]),
            },
        )
