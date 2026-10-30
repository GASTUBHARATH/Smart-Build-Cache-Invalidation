"""Persistent smart cache invalidation for small Python build graphs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Set, Union


@dataclass(frozen=True)
class ModuleSpec:
    """Describe a source module and the modules it depends on."""

    name: str
    source: Path
    dependencies: tuple[str, ...] = ()


@dataclass
class BuildStats:
    """Counters collected during one build."""

    total_modules: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    rebuilt_modules: List[str] = field(default_factory=list)


class SmartBuildCache:
    """Hash source files and rebuild only changed or affected modules."""

    CACHE_VERSION = 1

    def __init__(self, cache_dir: Union[Path, str] = "cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.metadata_path = self.cache_dir / "cache_metadata.json"
        self._metadata = self._load_metadata()

    @staticmethod
    def hash_file(path: Union[Path, str]) -> str:
        """Return the SHA-256 digest of a file."""

        digest = hashlib.sha256()
        with Path(path).open("rb") as source_file:
            for block in iter(lambda: source_file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def build(self, modules: Iterable[ModuleSpec]) -> BuildStats:
        """Build modules in dependency order and persist updated metadata."""

        module_map = {module.name: module for module in modules}
        self._validate_dependencies(module_map)
        order = self._topological_order(module_map)
        stats = BuildStats(total_modules=len(order))
        invalidated: Set[str] = set()
        current_hashes: Dict[str, str] = {}

        for name in order:
            module = module_map[name]
            source_hash: Optional[str] = None
            try:
                source_hash = self.hash_file(module.source)
            except FileNotFoundError:
                print("CACHE MISS: {} (source file missing)".format(name))
                self._metadata["modules"].pop(name, None)
                invalidated.add(name)
                stats.cache_misses += 1
                continue

            current_hashes[name] = source_hash
            cached = self._metadata["modules"].get(name)
            dependencies_changed = any(
                dependency in invalidated for dependency in module.dependencies
            )
            cache_hit = (
                cached is not None
                and cached.get("source_hash") == source_hash
                and cached.get("dependencies") == list(module.dependencies)
                and not dependencies_changed
            )

            if cache_hit:
                print("CACHE HIT: {}".format(name))
                stats.cache_hits += 1
                continue

            reason = "dependency changed" if dependencies_changed else "source changed"
            if cached is None:
                reason = "no cached result"
            print("CACHE MISS: {} ({})".format(name, reason))
            dependency_hashes = [
                current_hashes.get(dependency, "")
                for dependency in module.dependencies
            ]
            build_hash = self._build_hash(source_hash, dependency_hashes)
            self._metadata["modules"][name] = {
                "source_hash": source_hash,
                "dependencies": list(module.dependencies),
                "build_hash": build_hash,
            }
            invalidated.add(name)
            stats.cache_misses += 1
            stats.rebuilt_modules.append(name)

        self._save_metadata()
        self._print_statistics(stats)
        return stats

    def _load_metadata(self) -> dict:
        if not self.metadata_path.exists():
            return {"version": self.CACHE_VERSION, "modules": {}}
        try:
            with self.metadata_path.open("r", encoding="utf-8") as metadata_file:
                metadata = json.load(metadata_file)
            if (
                metadata.get("version") != self.CACHE_VERSION
                or not isinstance(metadata.get("modules"), dict)
            ):
                raise ValueError("unsupported cache metadata format")
            return metadata
        except (OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
            print("Cache metadata is missing or corrupted; starting with an empty cache.")
            return {"version": self.CACHE_VERSION, "modules": {}}

    def _save_metadata(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = self.metadata_path.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as metadata_file:
            json.dump(self._metadata, metadata_file, indent=2, sort_keys=True)
            metadata_file.write("\n")
        temporary_path.replace(self.metadata_path)

    @staticmethod
    def _build_hash(source_hash: str, dependency_hashes: Iterable[str]) -> str:
        value = source_hash + "".join(dependency_hashes)
        return hashlib.sha256(value.encode("ascii")).hexdigest()

    @staticmethod
    def _validate_dependencies(module_map: Mapping[str, ModuleSpec]) -> None:
        for module in module_map.values():
            unknown = set(module.dependencies) - set(module_map)
            if unknown:
                raise ValueError(
                    "{} depends on unknown module(s): {}".format(
                        module.name, ", ".join(sorted(unknown))
                    )
                )

    @staticmethod
    def _topological_order(module_map: Mapping[str, ModuleSpec]) -> List[str]:
        order: List[str] = []
        visiting: Set[str] = set()
        visited: Set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                raise ValueError("Circular dependency detected at {}".format(name))
            if name in visited:
                return
            visiting.add(name)
            for dependency in module_map[name].dependencies:
                visit(dependency)
            visiting.remove(name)
            visited.add(name)
            order.append(name)

        for name in module_map:
            visit(name)
        return order

    @staticmethod
    def _print_statistics(stats: BuildStats) -> None:
        print("\nBuild statistics:")
        print("  Total modules: {}".format(stats.total_modules))
        print("  Cache hits: {}".format(stats.cache_hits))
        print("  Cache misses: {}".format(stats.cache_misses))
        print("  Rebuilt modules: {}".format(len(stats.rebuilt_modules)))