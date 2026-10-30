import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from smart_cache import ModuleSpec, SmartBuildCache


class SmartBuildCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.source_dir = root / "src"
        self.cache_dir = root / "cache"
        self.source_dir.mkdir()
        self.sources = {
            "Module A": self.source_dir / "module_a.py",
            "Module B": self.source_dir / "module_b.py",
            "Module C": self.source_dir / "module_c.py",
        }
        for name, path in self.sources.items():
            path.write_text("value = {!r}\n".format(name), encoding="utf-8")
        self.modules = [
            ModuleSpec("Module A", self.sources["Module A"]),
            ModuleSpec("Module B", self.sources["Module B"], ("Module A",)),
            ModuleSpec("Module C", self.sources["Module C"], ("Module B",)),
        ]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def build(self) -> tuple[SmartBuildCache, object, str]:
        output = StringIO()
        with redirect_stdout(output):
            cache = SmartBuildCache(self.cache_dir)
            stats = cache.build(self.modules)
        return cache, stats, output.getvalue()

    def test_initial_build_rebuilds_every_module(self) -> None:
        _, stats, output = self.build()
        self.assertEqual(stats.cache_hits, 0)
        self.assertEqual(stats.cache_misses, 3)
        self.assertEqual(stats.rebuilt_modules, ["Module A", "Module B", "Module C"])
        self.assertEqual(output.count("CACHE MISS"), 3)
        self.assertTrue((self.cache_dir / "cache_metadata.json").exists())

    def test_second_build_uses_all_cached_results(self) -> None:
        self.build()
        _, stats, output = self.build()
        self.assertEqual(stats.cache_hits, 3)
        self.assertEqual(stats.cache_misses, 0)
        self.assertEqual(stats.rebuilt_modules, [])
        self.assertEqual(output.count("CACHE HIT"), 3)

    def test_changed_file_is_a_cache_miss(self) -> None:
        self.build()
        self.sources["Module C"].write_text("value = 'changed'\n", encoding="utf-8")
        _, stats, output = self.build()
        self.assertEqual(stats.rebuilt_modules, ["Module C"])
        self.assertEqual(stats.cache_hits, 2)
        self.assertIn("CACHE MISS: Module C", output)

    def test_dependency_change_invalidates_dependents(self) -> None:
        self.build()
        self.sources["Module A"].write_text("value = 'changed'\n", encoding="utf-8")
        _, stats, _ = self.build()
        self.assertEqual(stats.rebuilt_modules, ["Module A", "Module B", "Module C"])
        self.assertEqual(stats.cache_hits, 0)

    def test_corrupted_metadata_is_replaced_safely(self) -> None:
        self.cache_dir.mkdir()
        metadata_path = self.cache_dir / "cache_metadata.json"
        metadata_path.write_text("{not valid json", encoding="utf-8")
        _, stats, output = self.build()
        self.assertEqual(stats.cache_misses, 3)
        self.assertIn("corrupted", output)
        with metadata_path.open(encoding="utf-8") as metadata_file:
            self.assertEqual(json.load(metadata_file)["version"], 1)

    def test_missing_source_is_reported_and_dependents_are_invalidated(self) -> None:
        self.build()
        self.sources["Module A"].unlink()
        _, stats, output = self.build()
        self.assertEqual(stats.cache_misses, 3)
        self.assertIn("source file missing", output)
        self.assertEqual(stats.rebuilt_modules, ["Module B", "Module C"])


if __name__ == "__main__":
    unittest.main()