"""Demonstrate smart cache invalidation for three dependent modules."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smart_cache import ModuleSpec, SmartBuildCache


def project_modules() -> list[ModuleSpec]:
    source_dir = Path(__file__).resolve().parent
    return [
        ModuleSpec("Module A", source_dir / "module_a.py"),
        ModuleSpec("Module B", source_dir / "module_b.py", ("Module A",)),
        ModuleSpec("Module C", source_dir / "module_c.py", ("Module B",)),
    ]


def main() -> None:
    SmartBuildCache(Path(__file__).resolve().parent.parent / "cache").build(
        project_modules()
    )


if __name__ == "__main__":
    main()