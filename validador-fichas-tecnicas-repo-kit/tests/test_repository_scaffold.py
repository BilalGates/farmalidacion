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

    def test_container_fixtures_are_not_hidden_by_the_data_volume(self) -> None:
        """Los fixtures inmutables deben quedar fuera del volumen de SQLite."""
        dockerfile = (ROOT / 'infra/backend.Dockerfile').read_text(encoding='utf-8')
        compose = (ROOT / 'compose.yaml').read_text(encoding='utf-8')

        self.assertIn('COPY data/examples /app/fixtures', dockerfile)
        self.assertIn('APP_DEMO_FIXTURE_PATH: /app/fixtures/omeprazole-demo.json', compose)
        self.assertIn('APP_SHOWCASE_FIXTURE_PATH: /app/fixtures/showcase-demo.json', compose)
        self.assertIn('APP_CORS_ALLOW_ORIGINS:', compose)
        self.assertIn('app-data:/app/data', compose)
        self.assertNotIn('/app/data/examples/', compose)

if __name__ == '__main__':
    unittest.main()
