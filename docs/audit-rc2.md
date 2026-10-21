# Correcciones posteriores a la auditoría rc.1

Candidato de fuente: **0.2.0rc2**. Este documento no
anuncia publicación ni concede derechos de licencia.

| Hallazgo | Corrección / evidencia automatizada |
| --- | --- |
| P2: init seguía symlinks | `localio.checked` y preflight completo antes de crear; regresiones `test_localio` |
| P2: artefactos JSON malformados | validación integral de esquema, modos, catálogo y rutas; errores `ProjectError` controlados |
| P2: JSON enlazado por hardlink | escritura temporal y `os.replace` compartidos por configuración, prompts, estándares, memoria y MCP |
| P2: RC nativa parecía estable | versión PEP 440 y traducciones nativas ordenadas antes de final, prueba `test_packaging` |
| P2: aviso de licencia propio ausente | **resuelto por decisión del titular**; `LICENSE` MIT completo, copyright 2026 SrLambda, metadata y paquetes sincronizados |
| P3: pruebas nativas insuficientes | suite Docker por caso ya ejecutada en runner; escenarios ampliados para reiniciar Engram y recuperar un registro después de desinstalar |

Las regresiones cubren ancestros simbólicos, ausencia
de efectos parciales ante rutas inválidas, conservación
de hardlinks ajenos, tipos inválidos y catálogos propios.
Las pruebas antiguas de Codex mantienen sus contratos;
los patchpoints pasan del módulo CLI al adaptador
`codex`, único dueño del lanzamiento nativo.
No se inicia un modelo ni editor real en esas pruebas.
Los escenarios Docker sí ejecutan Engram y gestores
nativos de paquetes sin conexión durante runtime.

## Orden correcto de versiones

| Plataforma | Candidato | Final futura |
| --- | --- | --- |
| Python / fuente | `0.2.0rc2` | `0.2.0` |
| Debian | `0.2.0~rc.2-1` | `0.2.0-1` |
| Arch | `0.2.0rc2-1` | `0.2.0-1` |

**Migración desde rc.1:** sus paquetes anteriores
usaban por error `0.2.0-1`, equivalente a una versión
final. Los gestores consideran rc.2 inferior a ese
paquete. Para probar rc.2 en una VM que tenga rc.1,
retira primero el paquete anterior y después instala
el nuevo; no elimines los repos ni sus `.pxp/`.
PXP no fuerza downgrades ni cambia ajustes del gestor.
La desinstalación no elimina la memoria del proyecto.

Las conversiones se prueban además con `dpkg` y
`vercmp` cuando esas herramientas están disponibles.
El manifiesto de build registra versiones fuente y
nativas. La licencia MIT propia se incluye en fuente,
wheel y paquetes nativos; Engram conserva su aviso.

Referencias: [PEP 440](https://packaging.python.org/en/latest/specifications/version-specifiers/),
[versión Debian](https://www.debian.org/doc/debian-policy/ch-controlfields.html#version)
y [PKGBUILD](https://man.archlinux.org/man/PKGBUILD.5.en).
