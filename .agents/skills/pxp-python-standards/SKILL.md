---
name: pxp-python-standards
description: Refactorizar o ampliar Python de PXP Harness con PEP 8, documentación en español y un máximo estricto de 50 caracteres por línea. Aplicar al editar este repositorio; en otros proyectos consultar primero su perfil local.
---

# Estándares Python de PXP

Conserva identificadores, comandos y textos de interfaz
existentes en inglés. Escribe documentación, comentarios
y docstrings en español profesional. No traduzcas datos
ni cambies modos, códigos de salida o semántica para
satisfacer el formato.

## Perfil y comprobación

- En este repositorio: PEP 8 y máximo 50 caracteres por
  línea Python, incluidos comentarios, cadenas y pruebas.
- Consulta `pxp standards show` en proyectos inicializados.
  No inicialices ni cambies su perfil sin autorización.
- Los perfiles propios viven en `.pxp/standards.json`;
  consulta el esquema y las limitaciones en `README.md`.
- Ejecuta `ruff check .`, `ruff format --check .` y
  `PYTHONPATH=src python -m unittest discover -s tests -v`.
- El formateador solo intenta respetar el límite. Divide
  cadenas con concatenación implícita; nunca cortes su
  valor ni añadas excepciones para ocultar líneas largas.
- Usa `pxp standards apply` solo con autorización para
  modificar el Python del proyecto. Después revisa el
  diff y ejecuta sus pruebas; Ruff no prueba semántica.

## Extensión del harness

Mantén el núcleo sin dependencias de ejecución nuevas.
Ruff es una herramienta externa de desarrollo. No
introduzcas shell, comandos configurables ni escritura
en configuraciones de herramientas ajenas. Las pruebas
nuevas deben fallar antes de implementar comportamiento.

La lengua de documentación requiere revisión humana:
Ruff comprueba presencia y forma, no que sea español.
