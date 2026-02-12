import tempfile
import unittest
from pathlib import Path

from imagesorter.infrastructure.project_store import INITIAL_PROJECT_NAME, ProjectStore


class ProjectStoreTests(unittest.TestCase):
    def test_normalize_project_name(self):
        store = ProjectStore(Path('/tmp/example'))
        self.assertEqual(store.normalize_project_name('  Demo_1  '), 'demo_1')
        with self.assertRaises(ValueError):
            store.normalize_project_name('bad name with spaces')
        with self.assertRaises(ValueError):
            store.normalize_project_name('../escape')

    def test_migrate_legacy_layout_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'input').mkdir(parents=True)
            (root / 'good').mkdir(parents=True)
            (root / 'input' / 'a.jpg').write_bytes(b'a')
            (root / 'good' / 'b.jpg').write_bytes(b'b')

            store = ProjectStore(root)
            migrated = store.migrate_legacy_layout_once()
            self.assertEqual(migrated, INITIAL_PROJECT_NAME)

            project_root = root / 'projects' / INITIAL_PROJECT_NAME
            self.assertTrue((project_root / 'unlabeled' / 'a.jpg').exists())
            self.assertTrue((project_root / 'good' / 'b.jpg').exists())

            # Idempotent second run.
            migrated_again = store.migrate_legacy_layout_once()
            self.assertEqual(migrated_again, INITIAL_PROJECT_NAME)
            self.assertTrue((project_root / 'unlabeled' / 'a.jpg').exists())
            self.assertTrue((root / '.projects_migration_v1.done').exists())


if __name__ == '__main__':
    unittest.main()
