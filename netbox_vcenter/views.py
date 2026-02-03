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
from dcim.models import Platform
from extras.models import Tag
from ipam.models import IPAddress
from virtualization.models import Cluster, VMInterface, VirtualMachine

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


def get_import_config() -> dict:
    """Get the import/sync configuration settings."""
    config = settings.PLUGINS_CONFIG.get("netbox_vcenter", {})
    return {
        "normalize_name": config.get("normalize_imported_name", True),
        "default_tag": config.get("default_tag", ""),
        "default_role": config.get("default_role", ""),
        "default_platform": config.get("default_platform", ""),
    }


def get_name_for_import(vm_name: str, normalize: bool, mode: str, pattern: str) -> str:
    """
    Get the name to use when importing a VM.

    Args:
        vm_name: Original vCenter VM name
        normalize: Whether to normalize (strip domain, lowercase)
        mode: Name matching mode for normalization
        pattern: Regex pattern for regex mode

    Returns:
        Name to use in NetBox
    """
    if normalize:
        return normalize_name(vm_name, mode, pattern)
    return vm_name


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
            # Default to "all" if multiple servers have data, otherwise first server with data
            servers_with_data = [s for s in servers if cached_data.get(s)]
            if len(servers_with_data) > 1:
                selected_server = "all"
            elif servers_with_data:
                selected_server = servers_with_data[0]
            elif servers:
                selected_server = servers[0]

        # Get VMs for selected server (or all servers)
        if selected_server == "all":
            # Combine VMs from all servers
            vms = []
            for server in servers:
                server_data = cached_data.get(server)
                if server_data:
                    for vm in server_data.get("vms", []):
                        vm_copy = vm.copy()
                        vm_copy["source_server"] = server
                        vms.append(vm_copy)
        else:
            selected_data = cached_data.get(selected_server) if selected_server else None
            vms = selected_data.get("vms", []) if selected_data else []
            for vm in vms:
                vm["source_server"] = selected_server

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
        update_existing = form.cleaned_data.get("update_existing", False)

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

        # Get import configuration
        import_config = get_import_config()
        normalize_names = import_config["normalize_name"]
        default_tag_slug = import_config["default_tag"]
        default_role_slug = import_config["default_role"]
        default_platform_slug = import_config["default_platform"]

        # Look up default tag, role, platform if configured
        default_tag = None
        default_role = None
        default_platform = None

        if default_tag_slug:
            try:
                default_tag = Tag.objects.get(slug=default_tag_slug)
            except Tag.DoesNotExist:
                logger.warning(f"Default tag '{default_tag_slug}' not found in NetBox")

        if default_role_slug:
            try:
                from dcim.models import DeviceRole
                default_role = DeviceRole.objects.get(slug=default_role_slug)
            except Exception:
                logger.warning(f"Default role '{default_role_slug}' not found in NetBox")

        if default_platform_slug:
            try:
                default_platform = Platform.objects.get(slug=default_platform_slug)
            except Platform.DoesNotExist:
                logger.warning(f"Default platform '{default_platform_slug}' not found in NetBox")

        # Build map of normalized names to existing NetBox VMs
        existing_vm_map = {}
        for vm in VirtualMachine.objects.all():
            normalized = normalize_name(vm.name, match_mode, match_pattern)
            existing_vm_map[normalized] = vm

        # Import/Update VMs
        created = 0
        updated = 0
        skipped = 0
        errors = []

        for vm_data in vms_to_import:
            vm_name = vm_data.get("name")
            vm_normalized = normalize_name(vm_name, match_mode, match_pattern)

            # Determine name to use for import
            import_name = get_name_for_import(vm_name, normalize_names, match_mode, match_pattern)

            # Check if VM already exists
            existing_vm = existing_vm_map.get(vm_normalized)

            if existing_vm:
                if update_existing:
                    try:
                        # Update existing VM specs
                        existing_vm.vcpus = vm_data.get("vcpus")
                        existing_vm.memory = vm_data.get("memory_mb")
                        existing_vm.disk = vm_data.get("disk_gb")
                        existing_vm.status = "active" if vm_data.get("power_state") == "on" else "offline"

                        # Update role and platform if configured and not already set
                        if default_role and not existing_vm.role:
                            existing_vm.role = default_role
                        if default_platform and not existing_vm.platform:
                            existing_vm.platform = default_platform

                        # Update primary IP if available
                        primary_ip = vm_data.get("primary_ip")
                        if primary_ip:
                            self._update_vm_primary_ip(existing_vm, primary_ip)

                        existing_vm.full_clean()
                        existing_vm.save()

                        # Add tag if configured
                        if default_tag:
                            existing_vm.tags.add(default_tag)

                        updated += 1
                    except Exception as e:
                        errors.append(f"{vm_name}: {str(e)}")
                        logger.error(f"Error updating VM {vm_name}: {e}")
                else:
                    skipped += 1
                continue

            try:
                # Determine status based on power state
                status = "active" if vm_data.get("power_state") == "on" else "offline"

                # Create the VM with normalized or original name
                vm = VirtualMachine(
                    name=import_name,
                    cluster=cluster,
                    vcpus=vm_data.get("vcpus"),
                    memory=vm_data.get("memory_mb"),
                    disk=vm_data.get("disk_gb"),
                    status=status,
                    role=default_role,
                    platform=default_platform,
                    comments=f"Imported from vCenter {server} on {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                )
                vm.full_clean()
                vm.save()

                # Add tag if configured
                if default_tag:
                    vm.tags.add(default_tag)

                # Set primary IP if available
                primary_ip = vm_data.get("primary_ip")
                if primary_ip:
                    self._update_vm_primary_ip(vm, primary_ip)

                created += 1

            except Exception as e:
                errors.append(f"{vm_name}: {str(e)}")
                logger.error(f"Error importing VM {vm_name}: {e}")

        # Build result message
        if created:
            messages.success(request, f"Created {created} VM(s) in cluster '{cluster.name}'")
        if updated:
            messages.success(request, f"Updated {updated} existing VM(s)")
        if skipped:
            messages.info(request, f"Skipped {skipped} VM(s) (already exist, update not selected)")
        if errors:
            messages.warning(request, f"Failed: {len(errors)} VM(s): {'; '.join(errors[:3])}")

        return redirect("plugins:netbox_vcenter:dashboard")

    def _update_vm_primary_ip(self, vm, ip_address):
        """
        Update or create the primary IP address for a VM.

        Creates a VMInterface if needed, then creates/updates the IPAddress.
        """
        if not ip_address:
            return

        # Skip IPv6 link-local addresses
        if ip_address.startswith("fe80:"):
            return

        # Get or create the default interface
        interface, _ = VMInterface.objects.get_or_create(
            virtual_machine=vm,
            name="eth0",
            defaults={"enabled": True},
        )

        # Determine if IPv4 or IPv6
        is_ipv6 = ":" in ip_address

        # Add CIDR notation if not present
        if "/" not in ip_address:
            ip_address = f"{ip_address}/32" if not is_ipv6 else f"{ip_address}/128"

        # Get or create the IP address
        ip_obj, created = IPAddress.objects.get_or_create(
            address=ip_address,
            defaults={"assigned_object": interface},
        )

        # If IP exists but not assigned to this interface, update it
        if not created and ip_obj.assigned_object != interface:
            ip_obj.assigned_object = interface
            ip_obj.save()

        # Set as primary IP on the VM
        if is_ipv6:
            if vm.primary_ip6 != ip_obj:
                vm.primary_ip6 = ip_obj
                vm.save()
        else:
            if vm.primary_ip4 != ip_obj:
                vm.primary_ip4 = ip_obj
                vm.save()


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


class SyncDifferencesView(View):
    """Sync all VMs with spec differences from vCenter to NetBox."""

    def post(self, request):
        """Sync VMs that have differences between vCenter and NetBox."""
        server = request.POST.get("server", "")

        if not server:
            messages.error(request, "No server specified")
            return redirect("plugins:netbox_vcenter:compare")

        # Get cached vCenter data
        cached_data = get_cached_data(server)
        if not cached_data:
            messages.error(request, f"No cached data for {server}. Please sync first.")
            return redirect(f"/plugins/vcenter/compare/?server={server}")

        vcenter_vms = cached_data.get("vms", [])

        # Get name matching config
        match_mode, match_pattern = get_name_match_config()

        # Get import config for tag/role/platform
        import_config = get_import_config()
        default_tag_slug = import_config["default_tag"]

        default_tag = None
        if default_tag_slug:
            try:
                default_tag = Tag.objects.get(slug=default_tag_slug)
            except Tag.DoesNotExist:
                pass

        # Build maps
        vcenter_normalized_map = {}
        for vm in vcenter_vms:
            name = vm.get("name", "")
            normalized = normalize_name(name, match_mode, match_pattern)
            vcenter_normalized_map[normalized] = vm

        netbox_normalized_map = {}
        for vm in VirtualMachine.objects.all():
            normalized = normalize_name(vm.name, match_mode, match_pattern)
            netbox_normalized_map[normalized] = vm

        # Find VMs in both
        in_both = set(vcenter_normalized_map.keys()) & set(netbox_normalized_map.keys())

        updated = 0
        errors = []

        for normalized in in_both:
            vc_vm = vcenter_normalized_map.get(normalized)
            nb_vm = netbox_normalized_map.get(normalized)

            if not vc_vm or not nb_vm:
                continue

            # Check if there are differences
            has_diff = (
                vc_vm.get("vcpus") != nb_vm.vcpus
                or vc_vm.get("memory_mb") != nb_vm.memory
                or vc_vm.get("disk_gb") != nb_vm.disk
            )

            if not has_diff:
                continue

            try:
                # Update NetBox VM with vCenter specs
                nb_vm.vcpus = vc_vm.get("vcpus")
                nb_vm.memory = vc_vm.get("memory_mb")
                nb_vm.disk = vc_vm.get("disk_gb")
                nb_vm.status = "active" if vc_vm.get("power_state") == "on" else "offline"

                nb_vm.full_clean()
                nb_vm.save()

                # Add tag if configured
                if default_tag:
                    nb_vm.tags.add(default_tag)

                updated += 1
            except Exception as e:
                errors.append(f"{nb_vm.name}: {str(e)}")
                logger.error(f"Error syncing VM {nb_vm.name}: {e}")

        if updated:
            messages.success(request, f"Synced {updated} VM(s) from {server}")
        if errors:
            messages.warning(request, f"Failed: {len(errors)} VM(s): {'; '.join(errors[:3])}")
        if not updated and not errors:
            messages.info(request, "No VMs needed syncing")

        return redirect(f"/plugins/vcenter/compare/?server={server}")
