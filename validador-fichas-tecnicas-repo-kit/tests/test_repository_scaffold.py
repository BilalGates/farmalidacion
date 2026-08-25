import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryScaffoldTests(unittest.TestCase):
    def test_phase_one_boundaries_exist(self) -> None:
        expected = (
            'backend/README.md',
            'frontend/README.md',
            'infra/README.md',
            'data/examples/README.md',
            'docs/COMMANDS.md',
            '.env.example',
        )

        for relative_path in expected:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_environment_example_has_no_secret_values(self) -> None:
        content = (ROOT / '.env.example').read_text(encoding='utf-8')
        forbidden = ('PASSWORD=', 'SECRET=', 'TOKEN=', 'API_KEY=')

        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, content.upper())


if __name__ == '__main__':
    unittest.main()
