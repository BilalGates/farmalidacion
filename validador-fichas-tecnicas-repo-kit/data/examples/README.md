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
