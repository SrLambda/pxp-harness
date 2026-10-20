# Memoria local con Engram

Los paquetes de prueba 0.2.0 para Debian amd64 y
Arch x86_64 incluyen Engram 3.5.1 privado. La memoria
está DESACTIVADA hasta que la actives en cada repo.
Codex sigue siendo un requisito separado; no se
incluyen credenciales ni se inicia sesión por ti.

## Uso

Dentro del proyecto:

```sh
pxp init
pxp memory enable
pxp memory show
pxp chat "Continúa el proyecto"
pxp memory disable
```

Desde un checkout o instalación Python sin binario
incluido, selecciona explícitamente Engram instalado:

```sh
pxp memory enable --executable /ruta/absoluta/engram
```

Se guarda la preferencia en `.pxp/memory.json` y los
datos en `.pxp/engram/`. No compartas la base SQLite:
puede contener información privada. Añade esta línea
al `.gitignore` de cada proyecto:

```gitignore
.pxp/engram/
```

Desactivar conserva datos y no borra recuerdos.
Una ruta explícita se mantiene absoluta: en otra
máquina vuelve a configurarla o usa el binario del
paquete. No se busca Engram automáticamente en PATH.
Si está activado pero falta el ejecutable, el chat
falla con un mensaje antes de iniciar Codex.

## Integración y límites

El proceso Codex recibe opciones `-c` efímeras:
servidor MCP stdio `pxp_engram_<hash-del-repo>`,
comando absoluto, argumento `mcp`, cwd del proyecto y
`ENGRAM_DATA_DIR` absoluto de ese repo. No se ejecuta
`codex mcp add`, `engram setup` ni instaladores.
No se escribe configuración global o `.codex`.
Los prompts base siguen usando
`model_instructions_file` sin cambiar su contenido.

Se añade un protocolo corto mediante
`developer_instructions` para recordar consultar y
guardar contexto. Esto sustituye SOLO ese campo de
configuración durante el lanzamiento (si tenías otro
valor heredado, no se fusiona); no sustituye el prompt
base ni incorpora recuerdos en el pedido del usuario.
El servidor también publica instrucciones MCP.

Guardar y recuperar depende de que el modelo use las
herramientas: NO es garantía de guardado al terminar,
ni funciona si matas el proceso. No guardes secretos.
La separación por directorio evita mezclar bases por
accidente, pero no es una frontera de seguridad frente
a procesos con acceso al disco. Los permisos efectivos
por rol siguen pendientes; no se desactivan servidores
MCP globales previamente configurados. Engram local no
requiere nube, cuenta ni clave API. Se fuerza
`ENGRAM_CLOUD_AUTOSYNC=0` para evitar sincronización
heredada y se limpia el override `ENGRAM_PROJECT`.

## Reconstruir los paquetes incluidos

Python 3.11+, y makepkg para Arch. Descarga una sola
vez el asset fijado en `packaging/engram/lock.json`:

```sh
curl -fL \
  https://github.com/Gentleman-Programming/engram/releases/download/v3.5.1/engram_3.5.1_linux_amd64.tar.gz \
  -o /tmp/engram.tar.gz
python3 tools/package.py build \
  --engram-archive /tmp/engram.tar.gz \
  --output /tmp/pxp-engram-packages --arch
```

El builder verifica SHA256 y arquitectura ELF. Sin
`--engram-archive`, sigue disponible el paquete Python
sin Engram (`all`/`any`). El paquete con Engram usa
`amd64`/`x86_64`; otras arquitecturas no están incluidas.
No hay descargas ni actualización durante instalación.
El tar de fuentes y el bundle Arch contienen el asset
fijado, licencia y lock para reconstruir sin red.
Arch `check()` ejecuta las pruebas de PXP; no compila
Engram desde Go: redistribuye el binario upstream
verificado. El manifest identifica versión/origen/hash.

Se incluyen la licencia MIT original de Engram y su
aviso de copyright. La ausencia de una licencia
completa propia de PXP sigue indicada en NOTICE;
no se inventa una autorización adicional.

Fuentes: [Engram v3.5.1](https://github.com/Gentleman-Programming/engram/releases/tag/v3.5.1)
y [MCP oficial de Codex](https://learn.chatgpt.com/docs/extend/mcp).
