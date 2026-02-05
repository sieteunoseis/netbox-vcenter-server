"""vCenter API client using pyvmomi."""

import logging
import ssl
from typing import Optional

from pyVim.connect import Disconnect, SmartConnect
from pyVmomi import vim, vmodl

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
        view_mgr = self.content.viewManager.CreateContainerView(self.content.rootFolder, [obj_type], True)
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
        Fetch all virtual machines from vCenter using PropertyCollector.

        Uses PropertyCollector for efficient batch retrieval of VM properties,
        which is significantly faster than iterating through VMs one-by-one,
        especially for large environments (1000+ VMs).

        Returns:
            List of VM dictionaries with details
        """
        logger.info(f"Fetching VMs from {self.server} using PropertyCollector")

        # Define the properties we need to fetch
        vm_properties = [
            "name",
            "runtime.powerState",
            "runtime.host",
            "config.hardware.numCPU",
            "config.hardware.memoryMB",
            "config.hardware.device",
            "config.guestFullName",
            "config.uuid",
            "guest.ipAddress",
            "guest.net",
        ]

        # Build property collector objects
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.VirtualMachine], True
        )

        try:
            # Create traversal spec to traverse the container view
            traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
                name="traverseEntities",
                path="view",
                skip=False,
                type=vim.view.ContainerView,
            )

            # Property spec - what properties to collect
            property_spec = vmodl.query.PropertyCollector.PropertySpec(
                type=vim.VirtualMachine,
                pathSet=vm_properties,
                all=False,
            )

            # Object spec - where to start and how to traverse
            object_spec = vmodl.query.PropertyCollector.ObjectSpec(
                obj=container,
                skip=True,
                selectSet=[traversal_spec],
            )

            # Filter spec combining property and object specs
            filter_spec = vmodl.query.PropertyCollector.FilterSpec(
                objectSet=[object_spec],
                propSet=[property_spec],
            )

            # Retrieve properties with pagination support for large datasets
            options = vmodl.query.PropertyCollector.RetrieveOptions(maxObjects=500)
            result = self.content.propertyCollector.RetrievePropertiesEx(
                specSet=[filter_spec],
                options=options,
            )

            # Collect all results (handles pagination via ContinueRetrievePropertiesEx)
            objects = []
            while result:
                objects.extend(result.objects)
                if result.token:
                    result = self.content.propertyCollector.ContinueRetrievePropertiesEx(
                        token=result.token
                    )
                else:
                    break

            logger.info(f"PropertyCollector returned {len(objects)} VMs")

            # Pre-fetch host -> cluster/datacenter mappings to avoid repeated lookups
            host_info_cache = self._build_host_info_cache()

            # Process the results
            vm_list = []
            for obj in objects:
                try:
                    vm_data = self._process_vm_properties(obj, host_info_cache)
                    if vm_data:
                        vm_list.append(vm_data)
                except Exception as e:
                    vm_name = "unknown"
                    for prop in obj.propSet or []:
                        if prop.name == "name":
                            vm_name = prop.val
                            break
                    logger.warning(f"Error processing VM {vm_name}: {e}")
                    continue

            logger.info(f"Fetched {len(vm_list)} VMs from {self.server}")
            return vm_list

        finally:
            container.Destroy()

    def _build_host_info_cache(self) -> dict:
        """
        Pre-fetch host -> cluster/datacenter mappings.

        This avoids walking the parent hierarchy for each VM, which is slow
        when done thousands of times.

        Returns:
            Dict mapping host moref key -> {"cluster": name, "datacenter": name}
        """
        cache = {}

        try:
            # Get all hosts with their parent info using PropertyCollector
            container = self.content.viewManager.CreateContainerView(
                self.content.rootFolder, [vim.HostSystem], True
            )

            try:
                traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
                    name="traverseEntities",
                    path="view",
                    skip=False,
                    type=vim.view.ContainerView,
                )

                property_spec = vmodl.query.PropertyCollector.PropertySpec(
                    type=vim.HostSystem,
                    pathSet=["name", "parent"],
                    all=False,
                )

                object_spec = vmodl.query.PropertyCollector.ObjectSpec(
                    obj=container,
                    skip=True,
                    selectSet=[traversal_spec],
                )

                filter_spec = vmodl.query.PropertyCollector.FilterSpec(
                    objectSet=[object_spec],
                    propSet=[property_spec],
                )

                result = self.content.propertyCollector.RetrievePropertiesEx(
                    specSet=[filter_spec],
                    options=vmodl.query.PropertyCollector.RetrieveOptions(),
                )

                # Process host results
                host_objects = []
                while result:
                    host_objects.extend(result.objects)
                    if result.token:
                        result = self.content.propertyCollector.ContinueRetrievePropertiesEx(
                            token=result.token
                        )
                    else:
                        break

                for host_obj in host_objects:
                    host_key = str(host_obj.obj)
                    host_parent = None

                    for prop in host_obj.propSet or []:
                        if prop.name == "parent":
                            host_parent = prop.val

                    if host_parent:
                        info = {"cluster": None, "datacenter": None}

                        # Check if parent is a cluster
                        if isinstance(host_parent, vim.ClusterComputeResource):
                            info["cluster"] = host_parent.name

                        # Walk up to find datacenter
                        parent = host_parent
                        while parent:
                            if isinstance(parent, vim.Datacenter):
                                info["datacenter"] = parent.name
                                break
                            parent = getattr(parent, "parent", None)

                        cache[host_key] = info

            finally:
                container.Destroy()

        except Exception as e:
            logger.warning(f"Error building host info cache: {e}")

        return cache

    def _process_vm_properties(self, obj, host_info_cache: dict) -> dict:
        """
        Process PropertyCollector result for a single VM.

        Args:
            obj: PropertyCollector ObjectContent for a VM
            host_info_cache: Pre-built host -> cluster/datacenter mapping

        Returns:
            VM data dictionary
        """
        vm_data = {
            "name": None,
            "power_state": "off",
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

        # Extract properties from the result
        props = {prop.name: prop.val for prop in (obj.propSet or [])}

        vm_data["name"] = props.get("name")

        # Power state
        power_state = props.get("runtime.powerState")
        if power_state:
            vm_data["power_state"] = "on" if str(power_state) == "poweredOn" else "off"

        # Hardware config
        vm_data["vcpus"] = props.get("config.hardware.numCPU")
        vm_data["memory_mb"] = props.get("config.hardware.memoryMB")
        vm_data["guest_os"] = props.get("config.guestFullName")
        vm_data["uuid"] = props.get("config.uuid")

        # Calculate disk capacity from devices
        devices = props.get("config.hardware.device", [])
        if devices:
            disk_devices = [d for d in devices if isinstance(d, vim.vm.device.VirtualDisk)]
            if disk_devices:
                total_kb = sum(d.capacityInKB for d in disk_devices)
                vm_data["disk_gb"] = round(total_kb / 1048576)  # KB to GB

        # Primary IP from guest info
        primary_ip = props.get("guest.ipAddress")
        if primary_ip:
            vm_data["primary_ip"] = primary_ip
            vm_data["ip_addresses"].append(primary_ip)

        # Network interfaces from guest.net
        guest_net = props.get("guest.net")
        if guest_net:
            for nic in guest_net:
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

        # Get cluster and datacenter from host cache
        host = props.get("runtime.host")
        if host:
            host_key = str(host)
            host_info = host_info_cache.get(host_key, {})
            vm_data["cluster"] = host_info.get("cluster")
            vm_data["datacenter"] = host_info.get("datacenter")

        return vm_data

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
