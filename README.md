# Smart Build-Cache Invalidation

## Project overview

This project demonstrates a persistent build cache for a small Python module
graph. It uses SHA-256 file hashes and dependency tracking to rebuild only
modules whose source or dependencies changed.

## Problem statement

Rebuilding every module after every source edit wastes time. A build system
needs to recognize unchanged inputs, invalidate stale results, and propagate
changes through dependent modules.

## Objectives

- Detect source changes with SHA-256.
- Persist cache metadata as JSON.
- Reuse unchanged build results.
- Invalidate direct and transitive dependents.
- Report cache hits, misses, and build statistics.
- Handle missing files and corrupted metadata safely.

## Technologies

Python standard-library modules, SHA-256, JSON, GitHub Actions, and
`unittest`.

## Project structure

```text
src/
  main.py
  module_a.py
  module_b.py
  module_c.py
cache/
tests/
  test_cache.py
.github/workflows/python-tests.yml
smart_cache.py
README.md
.gitignore
```

`module_b` depends on `module_a`, and `module_c` depends on `module_b`.
`smart_cache.py` hashes sources, orders modules topologically, compares the
stored metadata, rebuilds invalidated modules, and writes the metadata
atomically.

## Installation

No third-party packages are required. Install Python 3.9 or newer and open a
terminal in the project directory.

## Execution

From the VS Code terminal on Windows, run:

```powershell
python src\main.py
```

The generated `cache\cache_metadata.json` file persists results between runs.

## Testing

Run all automated tests with:

```powershell
python -m unittest discover -s tests -v
```

The tests cover an initial build, all-cache-hit execution, source changes,
dependency invalidation, corrupted metadata, and missing source files.

## Expected results

1. The first execution reports three cache misses and rebuilds A, B, and C.
2. A second unchanged execution reports three cache hits and no rebuilds.
3. Changing `module_a.py` rebuilds A, B, and C.
4. Changing `module_c.py` rebuilds only C while A and B remain cache hits.