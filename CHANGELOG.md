# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.5.0 - 2025-05-07

### Added
- Add PredictIt scraper client for accessing market data.
- Binary contract filtering to only return markets with YES/NO contracts.
- Rate limit handling with respect for Retry-After header.
- Comprehensive test suite with mocked responses.

## 0.4.0 - 2025-05-06

### Added
- Add Nadex data client for accessing contracts and quotes.
- CSV parsing for contract listings with metadata extraction.
- Support for fetching individual contract details.
- Retry handling for rate limits and service unavailability.
- Comprehensive test suite with mocked responses.

## 0.3.0 - 2025-05-05

### Added
- Add Kalshi REST client for accessing market data.
- Support for both authenticated and public API endpoints.
- Automatic handling of rate limits with configurable retry logic.
- Comprehensive test suite with mocked responses.

## 0.2.0 - 2025-05-04

### Added
- Add venue normalizers for Kalshi, Nadex, and PredictIt.
- Support for converting venue-specific API responses to canonical MarketSnapshot format.
- Price normalization from venue-specific formats to probability (0-1).
- Test fixtures and comprehensive test suite for normalizers.

## 0.1.0 - 2025-05-04

### Added
- Add canonical data model (EventKey, Quote, MarketSnapshot).
- Serialization support for JSON with Decimal and datetime conversion.
- Comprehensive test suite for the data model classes.

## 0.0.0 - 2025-05-04

### Added
- Initial project scaffold: Poetry setup, directory structure, LICENSE.
- Code style: Ruff (lint), Black (format) with pre-commit hooks.
- Basic README.md and CHANGELOG.md.
- Placeholder sanity test.
