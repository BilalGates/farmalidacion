# Datos de ejemplo

Fixtures pequeños, sintéticos o derivados de referencias autorizadas para pruebas offline.

- No incluir datos de pacientes.
- No copiar originales de `data/reference/raw/`.
- Documentar procedencia, transformación y finalidad de cada fixture.
- Conservar bloques repetibles como ocurrencias separadas.

## Fixture ejecutable DEV-107

`omeprazole-demo.json` es sintético: no copia el Excel original ni contiene
datos de pacientes. Demuestra offline que dos ocurrencias repetibles con el
mismo valor literal mantienen identidad, orden y procedencia separados a través
de SQLite y `GET /records/{id}`.

La carga es idempotente y no sobrescribe colisiones. Compose la activa mediante
configuración explícita; el backend no la carga por defecto.

## Corpus sintético DEV-207

`cima-offline-corpus/` contiene dos versiones y cuatro cuerpos sintéticos
declarados en un manifiesto con hashes. Sus URLs `example.test` no representan
CIMA real. El fixture demuestra verificación, carga inmutable, reconstrucción y
diff con cualquier acceso de red bloqueado.

## Conjunto DEMO de la vertical de revisión

`showcase-demo.json` contiene cinco registros de **demostración**, generados de
forma determinista por `scripts/generate_showcase_fixture.py`.

- Los nombres de campo y de bloque proceden del catálogo real de 353
  definiciones. No se inventa semántica clínica.
- Los **valores no proceden de los maestros ni de CIMA**. Son de demostración.
- Todo identificador externo declara el sistema fuente `demo_showcase`, y el
  fixture lleva una `provenance_note`, para que un dato DEMO no pueda
  confundirse después con uno importado.
- Una discrepancia deliberada entre maestro y CIMA (`CANTIDAD` de DEMO-0002) se
  representa como dos afirmaciones con procedencia distinta, nunca como un valor
  ya elegido.
- Los bloques repetibles conservan ocurrencias separadas con su ordinal.
- La carga es idempotente y no sobrescribe contenido divergente.
- No se ha modificado ningún fichero original de referencia.

El backend no lo carga por defecto: requiere `APP_LOAD_SHOWCASE_FIXTURE=true`.

