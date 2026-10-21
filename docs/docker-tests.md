# Cada prueba en un contenedor nuevo

La suite Docker crea una imagen de preparación y
lanza **un contenedor efímero por ID unittest**.
El descubrimiento de pruebas ocurre dentro de Docker,
no importando los tests en el runner anfitrión.
También prueba wheel instalado y Engram MCP real con
dos stores separados. No usa modelos ni credenciales.

## GitHub Actions

En Actions, selecciona **Docker isolated tests**,
**Run workflow**, rama **main**, suite **unit** o
**full** (o **native** para repetir solo los dos
escenarios nativos). Solo se admite ejecución manual de este repo
y esa rama sobre `[self-hosted, Linux, X64]`.
No existe trigger de pull requests ni checkout de
código de forks. Un administrador debe mantener la
rama confiable y el runner dedicado; Docker comparte
el kernel y no convierte código hostil en seguro.

- `unit`: todos los IDs unittest descubiertos más
  wheel y Engram, cada uno en un contenedor nuevo.
- `full`: lo anterior más instalación/desinstalación
  real Debian y Arch, una por contenedor independiente.

El número crece automáticamente con los tests del
repositorio. Actualmente son 104 unit tests: **106
contenedores de prueba** para unit, **108** para full,
además del descubrimiento y preparación. Prevé varios
minutos; la primera descarga/build puede tardar más.
Timeout por caso: 180 s; por imagen: 900 s; job: 45 min.
Ejecuciones concurrentes se encolan, no se cancelan.

El runner necesita Docker operativo y Python 3.11+.
El workflow no instala Docker ni solicita sudo, ni
cambia grupos/permisos del socket. Acceso al daemon
es una capacidad potente del runner, no se concede a
los contenedores. No modifiques permisos del host para
hacer verde un test.

## Ejecución local

```sh
python3 tools/test_docker.py \
  --suite unit --report-dir /tmp/pxp-docker-result
```

El directorio de informes debe ser nuevo. Para probar
los dos gestores de paquetes usa `--suite full`.
`--suite native` ejecuta únicamente Debian y Arch,
sin repetir los unit tests.

No se hace limpieza global, `docker prune` ni borrado
de datos ajenos. Las imágenes/containers propios usan
UUID y se eliminan por nombre exacto. Un SIGKILL o
caída del daemon puede impedir la limpieza; revisa
solo recursos `pxp-ci-<uuid>`/`pxp-case-<uuid>` de esa
ejecución, nunca borres indiscriminadamente.

## Frontera de aislamiento

El contexto enviado al build es una lista explícita
de fuentes y recursos de empaquetado. No se monta el
checkout, `.git`, `.pxp`, HOME, credenciales, socket
Docker ni otros directorios del host. Se utiliza un
DOCKER_CONFIG temporal vacío, sin copiar login global.

Las imágenes preparan dependencias y descargan el
asset Engram fijado, comprobando su SHA256 **durante
build con red**. Las imágenes base Debian/Python y
Arch usan tags: no se promete reproducibilidad binaria
entre fechas; Actions checkout/upload sí están fijadas
por SHA completo. Arch prepara el paquete con makepkg
sin ejecutar tests durante el build (`--nocheck`):
las pruebas se ejecutan individualmente en runtime.

Runtime: `--network none`, `--cap-drop ALL`,
`no-new-privileges`, límites CPU/memoria/PIDs, sin
privileged ni mounts host. Unit/wheel/Engram usan UID
10001, root filesystem solo lectura y `/tmp` tmpfs.

**Excepción full:** instalar y quitar paquetes requiere
UID 0 y filesystem escribible, SOLO en la capa efímera
del contenedor Debian/Arch. Conserva los demás límites,
no recibe mounts ni acceso al daemon. Solo Arch
recupera `CAP_CHOWN` después de quitar las capabilities,
para que pacman gestione ownership de su directorio
temporal. No se desactiva el sandbox de pacman.
No instala nada
en el host ni modifica su configuración global.

Las pruebas de paquetes verifican launcher, activación
de memoria, conservación del sentinel Codex global y
datos del proyecto después de eliminar la aplicación.
No validan una sesión real de Codex o NeoVim. Tampoco
prueban permisos por rol; ese desarrollo sigue pendiente.

## Leer los resultados

El artifact `docker-results-<run>-<attempt>` contiene
`summary.json`, JUnit y un JSON por caso con estado,
exit code y log acotado/sanitizado. No publica entorno,
credenciales o rutas absolutas del host. La sanitización
es defensa adicional, no autorización para poner
secretos en fixtures.

PASS exige un caso ejecutado exitosamente. Skips,
expectedFailure y ausencia de marcador no dan verde.
Error de arranque/daemon/timeout es UNAVAILABLE y
hace fallar el proceso; no se omite silenciosamente.
Un test que falla se registra FAIL y no se reintenta.

Fuentes: [Docker run](https://docs.docker.com/engine/containers/run/)
y [seguridad de Actions](https://docs.github.com/en/actions/reference/security/secure-use).
