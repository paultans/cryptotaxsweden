# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **GitHub Actions CI** - Automated testing on Python 3.10, 3.11, 3.12
- **K4 2025 Template** - Added official K4 template for tax year 2025
- **Dynamic Template Fallback** - Automatically uses latest template for future years
- **Comprehensive Test Suite** - 38 unit tests covering tax computation, K4 generation, and USD/SEK rates
- **Type Hints** - Full type annotations on all core modules
- **Docstrings** - Documentation for all public functions and classes

### Changed
- **Python Version** - Updated minimum requirement to Python 3.10+
- **Dependencies** - Updated to latest stable versions:
  - pdfrw >= 0.4
  - Pillow >= 9.0.0
  - python-dateutil >= 2.8.0
  - reportlab >= 3.6.0
  - pytest >= 7.0.0 (dev)

### Fixed
- **USD/SEK Exchange Rates** - Updated from Riksbanken API (Jan 2010 - Jan 2026)

## [Previous Versions]

Historical changes were not tracked in a changelog.
