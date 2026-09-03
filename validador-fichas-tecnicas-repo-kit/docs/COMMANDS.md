# Superficie canónica de comandos

DEV-106 establece una única superficie de verificación para el repositorio.

| Comando conceptual | Finalidad | Estado |
|---|---|---|
| `test` | suite backend, frontend e integración | incluido en `verify` |
| `lint` | estilo estático de Python y TypeScript | Ruff y ESLint incluidos en `verify` |
| `typecheck` | tipos de backend y frontend | mypy estricto; TypeScript incluido en el build |
| `verify` | tests, lint, tipos, build, referencias, Compose y migraciones | `python scripts/verify_project.py` |
| `up` | levantar el entorno local | `docker compose up --build --detach --wait` |

El gate canónico completo es:

```text
python scripts/verify_project.py
```

Ejecuta pytest, Ruff, mypy estricto, Vitest, ESLint, build TypeScript/Vite,
validación de Compose, hashes de las ocho referencias y upgrade/downgrade de
Alembic sobre una base SQLite temporal.

En CI se usa `python scripts/verify_project.py --skip-references` porque los
originales verificados no se versionan ni están disponibles en el checkout
remoto; el resto del gate es idéntico.

Los comandos operativos de contenedores son:

```text
docker compose up --build --detach --wait
docker compose down
```

No deben crearse convenciones paralelas por componente.

El muestreo CIMA se ejecuta sobre páginas originales ya cacheadas y con una base
migrada, sin consultar la red:

```text
python -m pharma_validator_api.sampling --input pagina-1.json --input pagina-2.json --modo aleatorio --seed 203 --size 500 --output muestra.json
```

`--modo` es obligatorio (`aleatorio` o `estratificado`); no existe un modo del
piloto decidido por defecto mientras D-016 siga abierta.

El informe usa el manifiesto anterior y una respuesta original cacheada de
`/medicamento` por cada elemento seleccionado:

```text
python -m pharma_validator_api.composition_report --sample muestra.json --medication medicamento-1.json --medication medicamento-2.json --output-dir informe-composicion
```

El comando no consulta la red ni sobrescribe informes distintos existentes.

El diff compara dos versiones persistidas indicadas explícitamente:

```text
python -m pharma_validator_api.version_diff --old-version-id VERSION_1 --new-version-id VERSION_2 --output-dir informe-diff
```

El orden no implica vigencia regulatoria y un informe diferente existente no
se sobrescribe.

El corpus offline sintético se verifica sin escribir en base de datos:

```text
python -m pharma_validator_api.offline_corpus --corpus-dir data/examples/cima-offline-corpus
```

Para cargar un corpus verificado en la base configurada se añade `--load`. El
comando no descarga ni completa artefactos ausentes.

Una muestra previamente aprobada se descarga como corpus autocontenido con:

```text
python -m pharma_validator_api.corpus_capture --sample muestra.json --output-dir corpus-local
```

La repetición exige bytes idénticos y nunca sobrescribe un artefacto diferente.

El conjunto DEMO de la vertical de revisión se regenera de forma determinista:

```text
python scripts/generate_showcase_fixture.py
```

Su carga requiere activación explícita (`APP_LOAD_SHOWCASE_FIXTURE=true`); el
backend nunca carga datos de demostración por defecto.

