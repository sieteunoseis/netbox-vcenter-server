# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0] - 2026-11-20

### Added
- **Cluster sync** - New `sync_cluster` setting (default `False`) moves existing VMs to the cluster vCenter reports on "update existing" import and "Sync All Differences", and places newly imported VMs in it. The cluster name is taken as-is from vCenter: the VM's vSphere cluster, or its ESXi host's name when the host is standalone. The compare page flags cluster differences.
- **Auto-create clusters** - With `auto_create_clusters` (default `False`) and `auto_create_cluster_type` (an existing cluster type slug), a missing cluster is created, scoped to the NetBox site whose name or slug matches the vCenter datacenter.
- The ESXi host of each VM is now fetched and shown in the Cluster column for VMs on standalone hosts.

## [0.8.1] - 2026-11-20

### Fixed
- **Update existing VMs failed with `'str' object has no attribute 'version'`** - When "update existing" import created a new IP and set it as the VM's primary IP, the IP's address was still a plain string, so the VM's validation crashed. New IPs are now built with a proper network address.

### Changed
- `min_version` raised to NetBox 4.7.5 (the version this release was tested on).

## [0.8.0] - 2026-11-17

### Added
- `top_level_menu` setting (default `True`); set `False` to list this plugin's menu items under the shared "Plugins" menu instead of its own top-level sidebar menu

### Changed
- Plugin display name shortened to "vCenter" (was "NetBox vCenter") so it matches the sidebar menu label

## [0.7.0] - 2026-11-14

### Added
- **Primary IP in comparison** ([#15](https://github.com/sieteunoseis/netbox-vcenter-server/issues/15)) - "Compare with NetBox" now flags VMs whose vCenter primary IP differs from the NetBox VM's primary IP. "Sync All Differences" re-syncs those VMs' interfaces/IPs and repoints the primary IP (the old IP record is left in IPAM).
- **vCenter Notes import** ([#18](https://github.com/sieteunoseis/netbox-vcenter-server/issues/18)) - VM Notes (`config.annotation`) are fetched and used as the comments of newly imported VMs. New `sync_vm_notes` setting (default `False`) also pushes differing Notes to existing VMs on "update existing" import and "Sync All Differences", and shows them on the compare page.
- **Guest OS custom field** ([#16](https://github.com/sieteunoseis/netbox-vcenter-server/issues/16)) - New `guest_os_custom_field` setting names an existing Virtual Machine custom field to fill with the vCenter guest OS on import and sync.

### Fixed
- **Duplicate names in one import batch** ([#17](https://github.com/sieteunoseis/netbox-vcenter-server/issues/17)) - When two selected vCenter VMs normalize to the same NetBox name (e.g. `server01b` and `SERVER01b.example.com`), the second one failed with "Virtual machine name must be unique per cluster and tenant". It is now skipped and reported as a duplicate of the first.

### Changed
- `min_version` raised to NetBox 4.7.4 (the version this release was tested on).
- Compare page "Spec Differences" renamed to "Differences".

## [0.6.1] - 2026-09-03

### Fixed
- **"Sync all differences" disk validation failure** ([#14](https://github.com/sieteunoseis/netbox-vcenter-server/issues/14)) - Updating an existing VM's aggregate disk size (via import "update existing VMs" or the compare page's "Sync all differences") set `VirtualMachine.disk` and saved before syncing the VM's individual `VirtualDisk` records. NetBox validates the aggregate `disk` field against the sum of the VM's currently saved `VirtualDisk` records, so any VM whose per-disk sizes had changed in vCenter failed `full_clean()` with "The specified disk size (...) must match the aggregate size of assigned virtual disks (...)" and was silently left un-updated. Per-disk records are now synced first so the aggregate validates against up-to-date data. "Sync all differences" additionally never synced per-disk records at all (only the aggregate size) - it now does.

## [0.6.0] - 2026-08-28

### Added
- **Saved per-server credentials** ([#13](https://github.com/sieteunoseis/netbox-vcenter-server/issues/13)) - A new optional `vcenter_credentials` setting lets you configure a username/password per vCenter server in `PLUGINS_CONFIG` (intended for a dedicated read-only, non-MFA service account). When the selected server has saved credentials, the dashboard hides the manual username/password fields and syncs directly; servers without saved credentials still show the manual login form, so MFA-enabled accounts work exactly as before.

## [0.5.1] - 2026-08-25

### Added
- **Empty-config warning on dashboard** ([#12](https://github.com/sieteunoseis/netbox-vcenter-server/issues/12)) - When `PLUGINS_CONFIG["netbox_vcenter"]["vcenter_servers"]` is empty (e.g. missing/misconfigured), the dashboard previously showed nothing at all — an empty server dropdown and an empty Cache Status table, with no indication why. It now shows an explicit alert with the exact config key expected and common causes (wrong `PLUGINS_CONFIG` key, `configuration.py` not importing `PLUGINS_CONFIG` from a separate `plugins.py`, processes not restarted after a config change).

## [0.5.0] - 2026-08-13

### Fixed
- **Duplicate IP addresses on import** ([#11](https://github.com/sieteunoseis/netbox-vcenter-server/issues/11)) - VM interface import always searched IPAM for an exact `<host>/32` (or `/128`) match before creating a new `IPAddress`. If the host was already tracked in IPAM under its real subnet mask (e.g. `/24`), the string comparison missed it and a duplicate `/32` record was created. Lookups now match on the host address regardless of prefix length, and newly created records derive their prefix length from the most specific containing NetBox `Prefix` instead of hardcoding `/32`.

### Added
- **`default_vrf` and `default_tenant` settings** ([#11](https://github.com/sieteunoseis/netbox-vcenter-server/issues/11)) - Optional plugin settings to scope IP dedup/creation to a specific VRF and to tag newly created IP addresses with a tenant.
- **Pre-select discovered cluster on import** ([#9](https://github.com/sieteunoseis/netbox-vcenter-server/issues/9)) - The import screen's "Target Cluster" dropdown now defaults to the vCenter-discovered cluster (for single-VM or same-cluster bulk imports) when it maps to exactly one NetBox `Cluster`, while remaining fully editable.
- **Import dashboard search** ([#6](https://github.com/sieteunoseis/netbox-vcenter-server/issues/6)) - A live search box above the VM list filters by name, cluster, IP address, or datacenter. A new Datacenter column is also shown (already collected from vCenter but not previously surfaced). "Select all" now only selects VMs currently visible under the search filter.
- **Sync VM disks** ([#5](https://github.com/sieteunoseis/netbox-vcenter-server/issues/5)) - Each of a VM's hard disks is now synced as a NetBox `VirtualDisk` (name + size), on both import and update. Disks removed in vCenter are left untouched in NetBox rather than deleted.
- **Sync all VM interfaces** ([#3](https://github.com/sieteunoseis/netbox-vcenter-server/issues/3)) - All of a VM's network adapters are synced (not just the one holding the primary IP), each as a NetBox `VMInterface` with its MAC address, connected/enabled state, and IP address(es) attached. Interfaces are named to align with vSphere's own adapter numbering ("Network Adapter 1" -> `eth1`). IP lookups reuse the same host-based dedup as the primary-IP fix in #11, now applied per interface. Per-interface MTU is not synced yet (requires resolving the backing vSwitch/portgroup, deferred as a follow-up); interfaces removed in vCenter are left untouched in NetBox rather than deleted.

## [0.4.4] - 2026-06-17

### Fixed
- **Incorrect disk size** ([#8](https://github.com/sieteunoseis/netbox-vcenter-server/issues/8)) - NetBox stores `VirtualMachine.disk` in megabytes (it renders GB/TB on display via `DISK_BASE_UNIT`). The plugin was converting vSphere's KB capacity to **gigabytes** and writing that into the MB field, under-reporting disk size by ~1000x (e.g. a 1.6 TB VM showed as 1.66 GB). Disk capacity is now converted KB→MB. The `disk_gb` data key was renamed to `disk_mb` and the import/compare/dashboard tables now label the column in MB.

## [0.2.0] - 2026-02-03

### Added
- **Multi-vCenter Support** - Connect to multiple vCenter servers with separate caching
- **Import Dashboard** - Main dashboard for viewing and importing VMs from vCenter
- **VM Import** - Import selected VMs to NetBox with one click
- **Compare View** - Compare vCenter VMs with NetBox to find differences
- **Sync All Differences** - Bulk sync all VMs with spec differences
- **Name Matching Modes** - Configurable duplicate detection: exact, hostname, or regex
- **Import Settings** - Configure default tag, role, and platform for imported VMs
- **Name Normalization** - Optionally normalize VM names on import (strip domain, lowercase)
- **MFA/2FA Support** - Works with environments requiring multi-factor authentication

### Changed
- Renamed "Dashboard" to "Import Dashboard" for clarity
- Improved dark mode compatibility on Compare page

### Fixed
- Dark mode styling for "Only in NetBox" card on Compare page

## [0.1.0] - 2026-02-03

### Added
- Initial release
- Device tab view
- Virtual Machine tab view
- Settings page
- Caching support
