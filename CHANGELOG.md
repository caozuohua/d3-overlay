# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- BuildAssistant data pipeline script and generated `data/d3-data.json` artifact.
- BuildAssistant plugin with offline skill data rendering.
- Config reload/watch API and config change propagation to plugins and hotkeys.
- GitHub issues #2, #5, #6 tracking documentation.

### Changed
- Plugin crash handling now disables plugins after repeated render/update failures.
- Timer and Nemesis plugins accept typed events via EventBus while preserving backward compatibility.
- Hotkey reload/clear plumbing prepared for config-driven rebinding.

### Fixed
- Overlay font fallbacks standardized to `pygame.font.Font(None, size)` where file-backed fonts are unavailable.
- EventBus integration in `main.py` no longer creates per-frame duplicate bus instances.

## [0.2.0] - 2026-07-29

### Added
- v2 architecture prototypes: EventBus, SNO parser skeleton, font cache, MovableSystem, BossAlert.
- Blizzard API client extension with `get_hero_skills(class_slug)`.
- IcyVeins leveling guide scraper prototype.
- d3planner JS parser for `DiabloCalc.skills = {...}` blocks.

### Changed
- Test suite migrated to the project Python interpreter at `C:\Users\CAOZUO~1\AppData\Local\Python\bin\python.exe`.

## [0.1.0] - 2026-07-28

### Added
- Initial transparent overlay implementation with layered window support.
- Plugin system with Timer, BuildInfo, Nemesis, RiftInfo.
- Hotkey manager, config loader, game monitor, data provider.
- Documentation scaffolding in `docs/`.
