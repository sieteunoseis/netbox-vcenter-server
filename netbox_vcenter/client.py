"""vCenter API client using pyvmomi."""

import logging
import ssl
from typing import Optional

from pyVim.connect import Disconnect, SmartConnect
from pyVmomi import vim

logger = logging.getLogger(__name__)


class VCenterClient:
    """Client for connecting to VMware vCenter and fetching VM data."""

    def __init__(self, server: str, username: str, password: str, verify_ssl: bool = False):
        """
        Initialize vCenter client.

        Args:
            server: vCenter server hostname
            username: vCenter username (e.g., domain\\user)
            password: vCenter password
            verify_ssl: Whether to verify SSL certificates
        """
        self.server = server
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.service_instance = None
        self.content = None

    def connect(self):
        """
        Connect to vCenter server.

        Returns:
            ServiceInstance object

        Raises:
            Exception: If connection fails
        """
        logger.info(f"Connecting to vCenter: {self.server}")

        ssl_context = None
        if not self.verify_ssl:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        self.service_instance = SmartConnect(
            host=self.server,
            user=self.username,
            pwd=self.password,
            sslContext=ssl_context,
        )

        self.content = self.service_instance.RetrieveContent()
        logger.info(f"Connected to vCenter: {self.content.about.fullName}")

        return self.service_instance

    def disconnect(self):
        """Disconnect from vCenter server."""
        if self.service_instance:
            logger.info(f"Disconnecting from vCenter: {self.server}")
            Disconnect(self.service_instance)
            self.service_instance = None
            self.content = None

    def _get_objects_of_type(self, obj_type):
        """Get all objects of a specific type from vCenter."""
        view_mgr = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [obj_type], True
        )
        try:
            return list(view_mgr.view)
        finally:
            view_mgr.Destroy()

    def get_vcenter_info(self) -> dict:
        """Get vCenter server information."""
        about = self.content.about
        return {
            "name": about.name,
            "full_name": about.fullName,
            "version": about.version,
            "build": about.build,
            "os_type": about.osType,
        }

    def fetch_all_vms(self) -> list:
        """
        Fetch all virtual machines from vCenter.

        Returns:
            List of VM dictionaries with details
        """
        logger.info(f"Fetching VMs from {self.server}")

        vms = self._get_objects_of_type(vim.VirtualMachine)
        vm_list = []

        for vm in vms:
            try:
                vm_data = {
                    "name": vm.name,
                    "power_state": "on" if vm.runtime.powerState == "poweredOn" else "off",
                    "vcpus": None,
                    "memory_mb": None,
                    "disk_gb": None,
                    "cluster": None,
                    "datacenter": None,
                    "guest_os": None,
                    "uuid": None,
                    "ip_addresses": [],
                    "primary_ip": None,
                    "interfaces": [],
                }

                # Get hardware config
                if vm.config:
                    vm_data["vcpus"] = vm.config.hardware.numCPU
                    vm_data["memory_mb"] = vm.config.hardware.memoryMB
                    vm_data["guest_os"] = vm.config.guestFullName
                    vm_data["uuid"] = vm.config.uuid

                    # Calculate total disk capacity
                    disk_devices = [
                        device
                        for device in vm.config.hardware.device
                        if isinstance(device, vim.vm.device.VirtualDisk)
                    ]
                    if disk_devices:
                        total_kb = sum(d.capacityInKB for d in disk_devices)
                        vm_data["disk_gb"] = round(total_kb / 1048576)  # KB to GB

                # Get network interfaces and IP addresses from VMware Tools
                if vm.guest:
                    # Primary IP from guest info
                    if vm.guest.ipAddress:
                        vm_data["primary_ip"] = vm.guest.ipAddress
                        vm_data["ip_addresses"].append(vm.guest.ipAddress)

                    # Get all network interfaces
                    if vm.guest.net:
                        for nic in vm.guest.net:
                            interface = {
                                "name": nic.network or "Unknown",
                                "mac": nic.macAddress,
                                "connected": nic.connected,
                                "ip_addresses": [],
                            }
                            if nic.ipConfig and nic.ipConfig.ipAddress:
                                for ip_info in nic.ipConfig.ipAddress:
                                    ip = ip_info.ipAddress
                                    interface["ip_addresses"].append(ip)
                                    if ip not in vm_data["ip_addresses"]:
                                        vm_data["ip_addresses"].append(ip)
                            vm_data["interfaces"].append(interface)

                # Get cluster and datacenter
                if vm.runtime.host:
                    host = vm.runtime.host
                    if host.parent and isinstance(host.parent, vim.ClusterComputeResource):
                        vm_data["cluster"] = host.parent.name
                    # Walk up to find datacenter
                    parent = host.parent
                    while parent:
                        if isinstance(parent, vim.Datacenter):
                            vm_data["datacenter"] = parent.name
                            break
                        parent = getattr(parent, "parent", None)

                vm_list.append(vm_data)

            except Exception as e:
                logger.warning(f"Error processing VM {vm.name}: {e}")
                continue

        logger.info(f"Fetched {len(vm_list)} VMs from {self.server}")
        return vm_list

    def fetch_clusters(self) -> list:
        """
        Fetch all clusters from vCenter.

        Returns:
            List of cluster dictionaries
        """
        clusters = self._get_objects_of_type(vim.ClusterComputeResource)
        cluster_list = []

        for cluster in clusters:
            cluster_list.append(
                {
                    "name": cluster.name,
                    "host_count": len(cluster.host) if cluster.host else 0,
                }
            )

        return cluster_list

    def fetch_datacenters(self) -> list:
        """
        Fetch all datacenters from vCenter.

        Returns:
            List of datacenter dictionaries
        """
        datacenters = self._get_objects_of_type(vim.Datacenter)
        return [{"name": dc.name} for dc in datacenters]


def connect_and_fetch(
    server: str, username: str, password: str, verify_ssl: bool = False
) -> tuple[Optional[list], Optional[str]]:
    """
    Connect to vCenter and fetch all VMs.

    This is a convenience function that handles connection/disconnection.

    Args:
        server: vCenter server hostname
        username: vCenter username
        password: vCenter password
        verify_ssl: Whether to verify SSL certificates

    Returns:
        Tuple of (vm_list, error_message)
        - On success: (list of VMs, None)
        - On failure: (None, error message)
    """
    client = VCenterClient(server, username, password, verify_ssl)

    try:
        client.connect()
        vms = client.fetch_all_vms()
        return vms, None
    except vim.fault.InvalidLogin as e:
        logger.error(f"vCenter authentication failed: {e.msg}")
        return None, f"Authentication failed: Invalid username or password"
    except Exception as e:
        logger.error(f"vCenter connection failed: {e}")
        return None, f"Connection failed: {str(e)}"
    finally:
        client.disconnect()
