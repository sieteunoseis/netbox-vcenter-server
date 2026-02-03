# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
