# Verificar el sandbox en una VM

Este diagnóstico NO implementa permisos por rol.
Comprueba límites básicos del sandbox nativo sin
llamar a modelos, autenticarse ni acceder a Internet.
La protección de la política contra manipulación
sigue pendiente de validar con perfiles granulares.

## Ejecución en Debian o Arch

Como usuario normal, dentro de tu clon:

```sh
git pull --ff-only
python3 --version
type -a codex
```

Requiere Python 3.10 o posterior y Codex CLI ya
instalado. Selecciona la ruta ABSOLUTA del ejecutable
real de Codex. No uses un wrapper que ejecute
`npx`, instale paquetes o actualice automáticamente.
Por ejemplo, **si tu instalación lo tiene allí**:

```sh
python3 tools/check_sandbox.py \
  --codex /usr/bin/codex \
  --report sandbox-report.json
cat sandbox-report.json
```

No uses `sudo`. El informe debe ser un archivo nuevo:
el diagnóstico no sobrescribe informes existentes.
No lo añadas al repositorio; comparte solo su JSON.

## Interpretación

| Resultado | Significado |
| --- | --- |
| PASS / código 0 | Pasan los límites básicos probados. |
| FAIL / código 1 | Una operación contradice el límite esperado. |
| UNAVAILABLE / código 2 | No se pudo demostrar el límite. |

Se comprueba primero escritura y conexión TCP de
loopback sin sandbox. Después se exige que el proceso
sandboxed realmente arranque: escritura denegada en
solo lectura, escritura permitida en workspace y
conexión local denegada con red desactivada.

Un fallo de arranque, timeout o conexión rechazada
NO cuenta como una denegación correcta. El informe
omite rutas, usuarios, entorno y mensajes originales;
conserva versión, estado y motivo estable. No incluye
credenciales. Si aparece UNAVAILABLE, comprueba la
instalación de Codex y el soporte de sandbox de la VM;
no desactives el sandbox para obtener PASS.

El script usa temporales eliminados al finalizar y
un servidor TCP local, sin DNS ni salida externa.
No escribe configuración de Codex. La propia CLI
puede crear logs/estado normal al ejecutarse y carga
la configuración heredada: el resultado NO demuestra
una política aislada ni resistencia a escalación.
No comprueba MCP, plugins, apps ni protección de
`.pxp/permissions.json`; `policy_tamper` figura como
`NOT_TESTED`. No cambies permisos globales para esta
prueba.

## Próximo paso

Comparte el informe antes de activar permisos por rol.
Debe verificarse por separado que configuración
heredada, cambios de perfil y herramientas externas
no permitan eludir la política del proyecto.

Referencia: [permisos oficiales de Codex](https://learn.chatgpt.com/docs/permissions).
