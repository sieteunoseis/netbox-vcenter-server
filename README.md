# NetBox vCenter Server Plugin

<img src="docs/icon.png" alt="NetBox vCenter Server Plugin" width="100" align="right">

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
- **Duo MFA Support** - Works with environments requiring Duo authentication

## Requirements

- NetBox 4.0 or higher
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
        # Connection settings
        'timeout': 60,       # Timeout for vCenter connections (seconds)
        'verify_ssl': False, # SSL verification (False for self-signed certs)
        # MFA/2FA settings (optional)
        'mfa_enabled': True,  # Show MFA warning in UI
        'mfa_label': 'Duo',   # Label shown: "Duo", "2FA", "MFA"
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
    }
}
```

## Usage

### Syncing VMs from vCenter

1. Navigate to **Plugins > vCenter Dashboard**
2. Select a vCenter server from the dropdown
3. Enter your username and password
4. Click **Connect & Sync**
5. If Duo MFA is enabled, approve the push notification on your phone
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
   - **Spec Differences** - VMs with mismatched vCPUs, memory, or disk

## Screenshots

*Coming soon*

## Troubleshooting

### Connection errors

- Verify vCenter hostname is reachable from the NetBox server
- Check that credentials are correct (use `domain\username` format)
- For self-signed certificates, set `verify_ssl: False`
- If using Duo MFA, ensure you approve the push notification promptly

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
