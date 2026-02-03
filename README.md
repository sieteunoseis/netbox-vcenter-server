# NetBox Vcenter Plugin

<img src="docs/icon.png" alt="NetBox Vcenter Plugin" width="100" align="right">

A NetBox plugin for Vcenter integration.

![NetBox Version](https://img.shields.io/badge/NetBox-4.0+-blue)
![Python Version](https://img.shields.io/badge/Python-3.10+-green)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI](https://img.shields.io/pypi/v/netbox-vcenter)](https://pypi.org/project/netbox-vcenter/)

## Features

- **Device Tab** - Adds a "Vcenter" tab to Device detail pages
- **VM Tab** - Same functionality for Virtual Machines
- **Caching** - API responses are cached to improve performance

## Requirements

- NetBox 4.0 or higher
- Python 3.10+

## Installation

### From PyPI (recommended)

```bash
pip install netbox-vcenter
```

### From Source

```bash
git clone https://github.com/sieteunoseis/netbox-vcenter.git
cd netbox-vcenter
pip install -e .
```

### Docker Installation

Add to your NetBox Docker requirements file:

```bash
# requirements-extra.txt
netbox-vcenter
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
        # TODO: Add your settings
        'timeout': 30,
        'cache_timeout': 300,
        'verify_ssl': True,
    }
}
```

## Usage

Once installed and configured:

1. Navigate to any Device in NetBox
2. Click the **Vcenter** tab
3. View data from Vcenter

## Troubleshooting

### Connection errors

- Verify API URL is accessible from NetBox container
- Check that credentials are correct
- For self-signed certificates, set `verify_ssl: False`

## Development

### Setup

```bash
git clone https://github.com/sieteunoseis/netbox-vcenter.git
cd netbox-vcenter
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

sieteunoseis
