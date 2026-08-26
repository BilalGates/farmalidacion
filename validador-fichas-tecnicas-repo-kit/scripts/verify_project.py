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
    run('Configuración Compose', ['docker', 'compose', 'config', '--quiet'])
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
