#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NPM_COMMAND = 'npm.cmd' if os.name == 'nt' else 'npm'
NPM = shutil.which(NPM_COMMAND) or NPM_COMMAND


def run(label: str, command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f'==> {label}', flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def verify_compose_profiles() -> None:
    """Comprueba que cada modo levanta exactamente su pareja de aplicación."""
    for profile, expected in (
        ('demo', {'backend', 'frontend'}),
        ('real', {'backend-real', 'frontend-real'}),
        ('maintenance', {'maintenance-real'}),
    ):
        result = subprocess.run(
            ['docker', 'compose', '--profile', profile, 'config', '--services'],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        services = set(result.stdout.splitlines())
        if services != expected:
            raise RuntimeError(
                f'Perfil {profile}: servicios {sorted(services)}; '
                f'se esperaban {sorted(expected)}.'
            )
        print(f'==> Compose {profile}: {", ".join(sorted(services))}', flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Verificación integral del repositorio')
    parser.add_argument(
        '--skip-references',
        action='store_true',
        help='Omite originales locales no versionados; destinado exclusivamente a CI.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run('Tests Python', [sys.executable, '-m', 'pytest', 'tests', 'backend/tests'])
    run(
        'Lint Python',
        [
            sys.executable,
            '-m',
            'ruff',
            'check',
            'backend/src',
            'backend/tests',
            'backend/migrations',
            'scripts/verify_project.py',
            'scripts/run_cima_maintenance.py',
            'tests/test_run_cima_maintenance_cli.py',
        ],
    )
    run(
        'Tipos Python',
        [
            sys.executable,
            '-m',
            'mypy',
            '--config-file',
            'backend/pyproject.toml',
            'backend/src/pharma_validator_api',
        ],
    )
    run('Tests frontend', [NPM, '--prefix', 'frontend', 'run', 'test'])
    run('Lint frontend', [NPM, '--prefix', 'frontend', 'run', 'lint'])
    run('Build frontend', [NPM, '--prefix', 'frontend', 'run', 'build'])
    verify_compose_profiles()
    if not args.skip_references:
        run('Hashes de referencias', [sys.executable, 'scripts/verify_reference_files.py'])

    with tempfile.TemporaryDirectory(prefix='pharma-validator-migration-') as directory:
        database = Path(directory) / 'verify.db'
        migration_env = os.environ.copy()
        migration_env['APP_DATABASE_URL'] = f'sqlite:///{database.as_posix()}'
        alembic = [sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini']
        run('Alembic upgrade', [*alembic, 'upgrade', 'head'], env=migration_env)
        run('Alembic downgrade', [*alembic, 'downgrade', 'base'], env=migration_env)

    print('==> Verificación completa OK', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
