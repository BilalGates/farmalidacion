# Ficheros de referencia locales

Coloca aquí, sin renombrarlos, los ocho ficheros de entrada originales. Esta carpeta está ignorada por Git para evitar subir accidentalmente maestros voluminosos.

Ejecuta desde la raíz:

```bash
python scripts/verify_reference_files.py
```

El script valida nombre, tamaño aproximado y SHA-256. Si un fichero cambia de forma intencionada, registra la nueva versión y su procedencia en `docs/SOURCE_INVENTORY.md` antes de actualizar los hashes.
