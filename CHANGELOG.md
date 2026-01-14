# Changelog

## [Unreleased]
- All coins now use a single trainer file for speed and maintainability
- Removed trainer file copying to alt coin folders
- Improved shutdown: all trainers and scripts are terminated cleanly on app close
- Memory leak prevention: subprocesses and threads are stopped and cleaned up
- Added .gitignore for sensitive and cache files
