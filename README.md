# NetBox vCenter Server Plugin

<img src="https://raw.githubusercontent.com/sieteunoseis/netbox-vcenter-server/master/docs/icon.png" alt="NetBox vCenter Server Plugin" width="100" align="right">

A NetBox plugin for viewing and importing VMs from VMware vCenter servers.

![NetBox Version](https://img.shields.io/badge/NetBox-4.0+-blue)
![Python Version](https://img.shields.io/badge/Python-3.10+-green)
![vSphere Version](https://img.shields.io/badge/vSphere-8.0+-purple)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI](https://img.shields.io/pypi/v/netbox-vcenter-server)](https://pypi.org/project/netbox-vcenter-server/)

## Features

- **Multi-vCenter Support** - Connect to multiple vCenter servers (cached separately)
- **VM Dashboard** - View all VMs from vCenter with power state, vCPUs, memory, and disk
- **VM Import** - Import VMs from vCenter into NetBox with one click
- **Comparison View** - Compare vCenter VMs with NetBox to find differences
- **Manual Cache Control** - Data persists until you click Refresh
- **MFA/2FA Support** - Works with environments requiring multi-factor authentication

## Requirements

- NetBox 4.7.4 or higher (tested on 4.7.4)
- Python 3.10+
- VMware vSphere 7.0+ (tested with vSphere 8.0.3)

## Installation

### From PyPI (recommended)

```bash
pip install netbox-vcenter-server
```

### From Source

```bash
git clone https://github.com/sieteunoseis/netbox-vcenter-server.git
cd netbox-vcenter-server
pip install -e .
```

### Docker Installation

Add to your NetBox Docker requirements file:

```bash
# requirements-extra.txt
netbox-vcenter-server
```

## Configuration

Add the plugin to your NetBox configuration:

```python
# configuration.py or plugins.py

PLUGINS = [
    'netbox_vcenter',
]

PLUGINS_CONFIG = {
    'netbox_vcenter': {
        # Required: List of vCenter servers to choose from
        'vcenter_servers': [
            'vc-server1.example.com',
            'vc-server2.example.com',
        ],
        # Optional: saved credentials per server, to skip the manual login form.
        # Intended for a dedicated read-only service account that does not require
        # MFA - servers without an entry here still show the manual login form
        # (e.g. for MFA-enabled accounts).
        'vcenter_credentials': {
            'vc-server1.example.com': {
                'username': 'svc-netbox@vsphere.local',
                'password': 'changeme',
            },
        },
        # Connection settings
        'timeout': 60,       # Timeout for vCenter connections (seconds)
        'verify_ssl': False, # SSL verification (False for self-signed certs)
        # MFA/2FA settings (optional)
        'mfa_enabled': True,  # Show MFA warning in UI
        'mfa_label': 'MFA',   # Label shown in UI (e.g., "Duo", "2FA", "MFA")
        'mfa_message': 'Check your authenticator after clicking Connect & Sync.',
        # Name matching for duplicate detection
        # Options: "exact" (full name), "hostname" (strip domain), "regex"
        'name_match_mode': 'hostname',
        'name_match_pattern': r'^([^.]+)',  # Used with "regex" mode
        # Import settings
        'normalize_imported_name': True,  # "WebServer01.example.com" -> "webserver01"
        'default_tag': '',      # Tag slug to apply (e.g., "vcenter-sync")
        'default_role': '',     # Role slug (e.g., "server")
        'default_platform': '', # Platform slug (e.g., "vmware")
        'default_vrf': '',      # VRF name to scope IP dedup/creation (e.g., "management")
        'default_tenant': '',   # Tenant slug applied to IP addresses created during import
        # Sync vCenter VM Notes into comments of *existing* VMs (overwrites when they differ).
        # New imports always use the VM's Notes as comments when present.
        'sync_vm_notes': False,
        # Name of a Virtual Machine custom field (Text) to fill with the vCenter guest OS,
        # e.g. "Microsoft Windows Server 2022 (64-bit)". Create the custom field first.
        'guest_os_custom_field': '',
        # Sync each VM's cluster from vCenter (see "Cluster sync" below).
        'sync_cluster': False,
        'auto_create_clusters': False,
        'auto_create_cluster_type': '',  # Cluster type slug for auto-created clusters
    }
}
```

### Display Options

Optional `PLUGINS_CONFIG["netbox_vcenter"]` keys that control where the plugin appears in the UI:

| Setting | Default | Description |
|---------|---------|-------------|
| `top_level_menu` | `True` | `True` = own top-level sidebar menu. `False` = items listed under the shared **Plugins** menu, to shorten the sidebar. |

All of a VM's network adapters are synced, not just the primary one: each
becomes a NetBox `VMInterface` named to match vSphere's own adapter number
(vSphere's "Network Adapter 1" becomes NetBox interface `eth1`), with its
MAC address, connected/enabled state, and IP addresses attached. IP lookups
reuse an existing IPAM record for the address whenever one already exists
(regardless of its prefix length), instead of creating a duplicate `/32`.
When a new record does need to be created, its prefix length is derived
from the most specific containing NetBox `Prefix`. Set `default_vrf` if you
use VRFs, so lookups and new records stay scoped to the correct one; set
`default_tenant` to tag newly created IP addresses with a tenant.
Per-interface MTU is not synced yet (vSphere reports this at the
vSwitch/portgroup level, not directly on the adapter).

A VM's vCenter **Notes** become the NetBox comments of newly imported VMs.
Set `sync_vm_notes` to also push Notes changes to existing VMs (via "update
existing VMs" on import, or "Sync All Differences").

For the operating system, either map the vCenter guest OS to a NetBox
`Platform` with `platform_mappings`, or create a Text custom field on Virtual
Machine and set `guest_os_custom_field` to its name to store the guest OS
string as-is.

**Cluster sync.** With `sync_cluster` enabled, "update existing VMs" and
"Sync All Differences" move a VM to the NetBox cluster vCenter places it in,
and new imports go there too (the cluster picked in the import form is the
fallback). The cluster name is taken as-is from vCenter: the VM's vSphere
cluster, or its ESXi host's name when the host isn't in a cluster. If no NetBox
cluster has that exact name, the VM is left where it is, unless
`auto_create_clusters` is enabled; the cluster is then created with the
cluster type whose slug is `auto_create_cluster_type` and no site scope.
When a VM changes cluster, its host device is set to the NetBox device named
after its vCenter ESXi host if that device is in the new cluster, and cleared
otherwise (NetBox requires a VM's device to belong to its cluster). Re-sync from vCenter after upgrading so cached data includes each
VM's host.

Each of a VM's hard disks is also synced as a NetBox `VirtualDisk` (name and
size). Disks and interfaces removed from a VM in vCenter are left in place
in NetBox rather than deleted.

## Usage

### Syncing VMs from vCenter

1. Navigate to **Plugins > vCenter Dashboard**
2. Select a vCenter server from the dropdown
3. Enter your username and password
4. Click **Connect & Sync**
5. If MFA is enabled, approve the authentication prompt
6. VMs will be fetched and cached (data persists until you click Refresh)

### Importing VMs to NetBox

1. From the VM list, check the boxes next to VMs you want to import
2. Click **Import Selected to NetBox**
3. Select the target NetBox cluster
4. Click **Import**
5. VMs are created in NetBox with vCPUs, memory, disk, and status

### Comparing vCenter with NetBox

1. Navigate to **Plugins > Compare with NetBox**
2. Select a vCenter server
3. View:
   - **Only in vCenter** - VMs that can be imported
   - **Only in NetBox** - VMs not found in vCenter (orphaned?)
   - **Differences** - VMs with mismatched vCPUs, memory, disk, or primary IP
     (and Notes, when `sync_vm_notes` is enabled; cluster, when `sync_cluster` is enabled)
4. **Sync All Differences** updates those VMs in NetBox; a changed primary IP
   also re-syncs the VM's interfaces/IPs and repoints its primary IP (the old
   IP record is left in IPAM)

## Screenshots

*Coming soon*

## Troubleshooting

### Connection errors

- Verify vCenter hostname is reachable from the NetBox server
- Check that credentials are correct (use `domain\username` format)
- For self-signed certificates, set `verify_ssl: False`
- If using MFA/2FA, ensure you approve the authentication prompt promptly

### Authentication issues

- Use format `DOMAIN\username` or `username@domain`
- Ensure the account has at least read-only access to vCenter

## Development

### Setup

```bash
git clone https://github.com/sieteunoseis/netbox-vcenter-server.git
cd netbox-vcenter-server
pip install -e ".[dev]"
```

### Code Style

```bash
black netbox_vcenter/
isort netbox_vcenter/
flake8 netbox_vcenter/
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Support

If you find this plugin helpful, consider supporting development:

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow?style=flat&logo=buy-me-a-coffee)](https://buymeacoffee.com/automatebldrs)

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

## Author

sieteunoseis ([@sieteunoseis](https://github.com/sieteunoseis))
