# PXP Harness

PXP Harness añade modos y contexto de proyecto a Codex
CLI. Funciona localmente, también desde una terminal
SSH o Termux. No incluye un modelo de IA ni almacena
credenciales.

## Empezar

Desde el repositorio clonado:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pxp init
pxp mode
pxp mode implementation-code
pxp standards show
pxp chat "Implementa la siguiente tarea"
```

Python mínimo: 3.10. El núcleo usa solo la biblioteca
estándar. El extra `dev` instala Ruff 0.16.4; `init`,
`mode`, `show`, `configure` y `chat` no requieren Ruff.
Instala y autentica Codex por separado: PXP utiliza el
programa `codex` disponible en `PATH`.

## Chat en Codex y texto en NeoVim

`pxp chat` abre la **interfaz interactiva de terminal
(TUI) de Codex**. No es un chat propio de PXP ni usa
`codex exec`: invoca `codex` con el contexto inicial y
mantiene conectados teclado, pantalla y salida de
error del terminal.

```bash
pxp prompt edit plan
pxp prompt view plan
pxp chat "Revisa los requisitos"
```

Para editar o consultar el modo activo, omite `plan`.
`edit` abre NeoVim con tu configuración habitual. Si
no hay archivo asociado, prepara un borrador vacío en
`.pxp/prompts/<mode-id>.md` sin sobrescribir otro
archivo. Escribe tus instrucciones y guarda con
`:wq`: solo después de una salida correcta y texto
válido se activa como base del modo.

Si sales sin guardar un borrador nuevo (`:q!`), el
archivo vacío queda sin asociar y el comando indica
que no es válido. Si NeoVim falla, el borrador también
se conserva sin activar. Repite `edit` para continuar.
Un borrador anterior nunca se sobrescribe al abrirlo.
Para un archivo ya asociado se edita el original;
`:q!` descarta solo tus cambios no guardados. Si
eliminas su contenido y lo guardas, la validación
falla y `chat` no lo utilizará hasta que lo repares.
`edit` permite reparar un archivo asociado vacío.

`view` exige una asociación válida y abre NeoVim con
`--clean -R -M -n -i NONE`: sin configuración/plugins,
sin modificaciones del buffer, sin swap ni ShaDa.
También desactiva el archivo de log de esa vista.
No cambia contenido ni asociaciones por sí mismo.
Es prevención de escritura accidental, **no** una
frontera de seguridad frente a comandos manuales del
usuario. Puedes salir con `:q`.

Ambas acciones requieren `nvim` en `PATH`, mantienen
los archivos dentro del proyecto y rechazan enlaces
simbólicos. No usan shell y las rutas con espacios se
pasan como un solo argumento. Si falta NeoVim, PXP
indica cómo resolverlo sin crear borradores.

Dentro de la TUI de Codex, `Ctrl+G` abre NeoVim para
redactar una petición larga; guarda y cierra para
volver al compositor antes de enviarla. PXP establece
`VISUAL=nvim` y `EDITOR=nvim` solo en el proceso hijo
de Codex: no modifica tu shell ni configuración global.
Esto edita la **petición de usuario**, no el archivo
de instrucciones base. Este último se edita con
`pxp prompt edit`; sus cambios se cargan en el próximo
`pxp chat`, no en una sesión ya abierta.

Para otros textos locales, como los requisitos, puedes
usar directamente `nvim .pxp/artifacts/requirements.md`.
No se requiere otra interfaz gráfica. Referencias:
[TUI y editor de Codex](https://learn.chatgpt.com/docs/cli-customization),
[opciones de NeoVim](https://neovim.io/doc/user/starting.html).

## Crear un proyecto con Git

Desde una carpeta nueva, fuera de otro repositorio:

```bash
mkdir mi-proyecto
cd mi-proyecto
pxp init --git
pxp mode plan
```

`--git` comprueba si existe un repositorio de trabajo.
Si no existe, ejecuta `git init` local y después crea
la configuración PXP. Si ya existe, lo reutiliza sin
reinicializarlo: conserva historia, índice, ramas,
remotos y configuración. No crea commits, no configura
remotos, no autentica, no clona ni publica en GitHub.
Git decide la rama inicial con tu configuración normal.

El ejecutable `git` solo es obligatorio con `--git`.
PXP nunca modifica la configuración global de Git ni
hereda las variables `GIT_*` que podrían redirigir la
operación a otro repositorio. No cambia permisos y no
ejecuta comandos mediante shell.

## Añadir PXP a un proyecto existente

Entra en su carpeta y ejecuta:

```bash
cd mi-proyecto-existente
pxp init
pxp standards show
pxp prompt show
```

Esto funciona con o sin Git y no exige `--git`.
Añade únicamente la configuración local `.pxp/` y las
plantillas faltantes. Conserva el código, los commits,
los remotos, los artefactos existentes y los valores
de configuración PXP ya guardados. Puedes repetirlo.

Si el proyecto ya contiene `.pxp/config.json`, se lee
esa configuración; los comandos cargan también sus
perfiles y asociaciones de prompts existentes. No se
importa ni se copia automáticamente la configuración
de otro repositorio. Elige los estándares y archivos
base del proyecto con `standards configure` y
`prompt set`.

### Raíz del proyecto y subdirectorios

Dentro de Git, todos los comandos buscan la raíz del
repositorio para evitar crear otro `.git` o `.pxp`
accidentalmente en `src/` u otros subdirectorios.
También se admiten worktrees cuyo `.git` es un archivo.
Si hay un proyecto PXP configurado más cercano dentro
del mismo repositorio, se conserva ese límite en vez
de mover sus archivos. En ese caso, `init --git` falla
si la raíz PXP no coincide con la raíz Git; ejecuta el
comando desde la raíz Git o utiliza `init` sin el flag.
No se ofrece una opción para forzar repos anidados.

Fuera de Git se mantiene el comportamiento anterior:
los comandos usan el directorio actual. Una carpeta
`.git` vacía en un antecesor no identifica un repo.
No trabajes directamente en los metadatos `.git` ni en
repositorios bare: PXP espera un árbol de trabajo.

Un error de Git detiene la creación de `.pxp/` y
muestra una indicación para revisar la instalación,
los permisos o la configuración. No se intenta reparar
metadatos existentes ni borrar archivos ante un fallo.
Si Git alcanzó a crear metadatos antes del error, estos
pueden quedar en disco: revísalos antes de reintentar.
Si Git termina bien pero después falla la creación de
PXP, el repositorio Git también se conserva.

## Iniciar con instrucciones base propias

Para sustituir las instrucciones base incorporadas de
Codex en un modo, escribe tu propio archivo UTF-8 con
`prompt edit` o asocia uno existente con
`pxp prompt set plan prompts/plan.md`. PXP no genera
instrucciones ni exige configurar los nueve modos.

```bash
pxp init
pxp prompt edit plan
pxp prompt show plan
pxp mode plan
pxp chat "Revisa los requisitos"
```

`pxp prompt show` consulta el modo activo; con un modo
explícito consulta ese modo. Muestra únicamente la ruta
relativa, nunca el contenido del archivo.

La asociación se guarda en `.pxp/prompts.json`:

```json
{
  "plan": "prompts/plan.md",
  "implementation-code": "prompts/code.md"
}
```

Al iniciar `chat`, PXP valida el archivo y ejecuta el
equivalente de:

```bash
codex -c 'model_instructions_file="/ruta/plan.md"' \
  "Contexto del proyecto y petición del usuario"
```

La ruta enviada a Codex es absoluta y se serializa
como una cadena TOML, sin shell. El contenido del
archivo **no** se concatena a la petición del usuario.
La petición inicial conserva el contexto anterior:
modo, rutas de artefactos y estándares activos.

`model_instructions_file` reemplaza las instrucciones
base incorporadas; no es el ajuste aditivo
`developer_instructions` ni un mensaje de usuario.
Esto no elimina las restricciones del servicio, los
permisos del sistema, las aprobaciones o el sandbox.
No promete controlar todos los mensajes internos ni
crear una frontera de seguridad. Debes revisar tu
archivo: reemplazar las instrucciones base también
puede quitar orientación útil del agente.

Consulta la
[referencia oficial de configuración](https://learn.chatgpt.com/docs/config-file/config-reference)
y utiliza una versión de Codex que admita esa clave.
PXP no descarga ni actualiza Codex automáticamente.

Para dejar de aplicar el archivo en ese modo:

```bash
pxp prompt clear plan
```

`clear` solo elimina la asociación, nunca el archivo.
Un modo sin asociación conserva el lanzamiento previo
sin override de PXP y hereda la configuración normal
de Codex (incluido cualquier ajuste global propio).
El valor `null` en `show` significa que PXP no tiene
asociación; no inspecciona la configuración global.

Cambiar modo o asociación solo afecta al siguiente
`pxp chat`: no modifica una sesión ya iniciada.
No se escribe en `~/.codex/config.toml` ni se cambian
los permisos o los proveedores del usuario.

### Portabilidad y errores de archivo

Los archivos deben estar dentro de la raíz del
proyecto, sin enlaces simbólicos ni componentes `..`.
`set` acepta una ruta relativa o una absoluta interna
y guarda siempre la ruta relativa para trasladar el
repositorio entre PC, VM y móvil. No expande `~` ni
variables de entorno. Versiona el JSON y tus archivos
si quieres compartirlos; nunca incluyas secretos.

Se admite texto UTF-8 no vacío de hasta 1 MiB; se
rechazan directorios, binarios, controles no textuales
y archivos ilegibles, ausentes o vacíos. Se valida al
configurar y de nuevo antes de iniciar Codex. JSON
malformado, tipos incorrectos, claves de modo no
reconocidas o rutas externas fallan sin iniciar Codex.
Los errores no muestran el contenido del prompt.
`set` no cambia otros modos, estándares ni artefactos;
`init` no crea ni sobrescribe asociaciones existentes.

## Estándares por proyecto y perfil

El valor predeterminado es PEP 8, **50 caracteres por
línea Python** y documentación/docstrings en español.
La skill versionada está en
[SKILL.md](.agents/skills/pxp-python-standards/SKILL.md),
ruta de descubrimiento local de Codex. No modifica las
skills globales del usuario.

```bash
pxp standards show
pxp standards check
pxp standards apply
```

- `show`: muestra el perfil efectivo sin escribir.
- `check`: comprueba lint, formato y ancho estricto;
  devuelve 0 si todo pasa, 1 si falla.
- `apply`: ejecuta correcciones seguras de Ruff y el
  formateador; después repite las comprobaciones.
  Puede modificar archivos aunque termine con error.
  Revisa el diff y ejecuta tus pruebas después.

Ruff solo intenta respetar el ancho; E501 también
exceptúa algunas URL y palabras largas. Por eso el
harness añade una comprobación sin esas excepciones
(tabulaciones expandidas a ocho columnas). Una cadena
larga debe dividirse manualmente sin cambiar su valor.
No se aplican correcciones inseguras.

Se comprueban todos los `.py` bajo el directorio actual,
incluidos los tests; se omiten enlaces simbólicos y
`.git`, `.codegraph`, `.venv`, `venv`, `__pycache__`,
`node_modules`, `build`, `dist`, `.tox`, `.ruff_cache`.
No se siguen enlaces hacia otros proyectos. Usa un
entorno virtual llamado `.venv` o fuera del proyecto.

Las reglas nativas son `E,F,I,D` (PEP 8, errores,
importaciones y docstrings), salvo `D203,D213`, que
contradicen el estilo de docstring elegido. La lengua
se transmite a Codex, pero requiere revisión humana:
Ruff no determina si una frase está en español.

## Personalizar para otro proyecto

Instala PXP en su entorno y ejecuta los comandos desde
la raíz de ese proyecto. No cambia el perfil global ni
los perfiles de otros proyectos.

```bash
pxp init
pxp standards configure --profile portable
pxp standards configure --profile wide \
  --line-length 79 --doc-language en
pxp standards show
pxp standards check
pxp standards configure --profile portable
```

`configure` crea o selecciona un perfil. Los valores
omitidos conservan los de ese perfil; un perfil nuevo
parte del predeterminado (50, `es`). Si no pasas
`--profile`, configura y activa `default`. No hay
herencia entre perfiles. Los ajustes solo se aceptan
en `configure`, nunca como cambios implícitos de
`check`, `apply` o `show`.

La configuración es `.pxp/standards.json`:

```json
{
  "active_profile": "default",
  "profiles": {
    "default": {
      "line_length": 50,
      "doc_language": "es"
    },
    "wide": {
      "line_length": 79,
      "doc_language": "en"
    }
  }
}
```

Longitud válida: entero de 40 a 320; idiomas: `es` o
`en`; nombre: 1–40 letras ASCII, números, `_` o `-`.
Cada perfil debe tener exactamente esos dos campos.
JSON malformado, campos desconocidos, perfiles activos
inexistentes y configuraciones enlazadas se rechazan.
No admite comandos arbitrarios ni shell.

Versiona este JSON si quieres compartir los perfiles.
Los proyectos antiguos usan el predeterminado sin
migración: leer o inicializar no crea ni sobrescribe
este archivo. `configure` lo escribe explícitamente y
conserva los demás perfiles. `.pxp/config.json` y los
archivos de herramientas existentes no se modifican.

Para evitar resultados distintos por configuración
externa, el harness ejecuta Ruff con `--isolated` y
reglas fijas. No combina `pyproject.toml`, exclusiones
ni reglas personalizadas de Ruff de otro proyecto.
Los perfiles actuales personalizan ancho e idioma,
no un motor genérico de estilos o lenguajes. La skill
del harness no impone 50 columnas a otros proyectos:
allí se debe consultar primero el perfil efectivo.

## Modos y contexto

Los nueve identificadores anteriores se conservan:

| Identificador | Etapa |
|---|---|
| `plan` | Plan general |
| `design` | Diseño general |
| `iteration-initialization` | Inicio de iteración |
| `iteration-design` | Diseño de iteración |
| `implementation-tests` | Pruebas de implementación |
| `implementation-code` | Código de implementación |
| `implementation-refactor` | Refactorización |
| `system-tests` | Pruebas del sistema |
| `retrospective` | Retrospectiva |

`pxp mode` marca el modo activo y
`pxp mode <mode-id>` lo cambia. `pxp chat` comunica a
Codex el modo, el perfil y las rutas de cinco artefactos:

- `.pxp/artifacts/requirements.md`
- `.pxp/artifacts/rules.md`
- `.pxp/artifacts/architecture-design.md`
- `.pxp/artifacts/mockups.md`
- `.pxp/artifacts/data-model.md`

`pxp init` añade archivos faltantes sin sobrescribir
contenido existente. Los títulos de plantillas y textos
de interfaz se conservan en inglés por compatibilidad.
La configuración principal mantiene `schema_version: 1`.

## Paquetes nativos Debian y Arch

El builder local genera un `.deb` y una receta Arch
con su fuente y checksum. En Arch puede generar además
el `.pkg.tar.zst` con **makepkg real**. No instala nada,
no requiere root y no descarga fuentes/dependencias.
La versión sale de `pyproject.toml`; el empaquetado
actual admite versiones estables `X.Y.Z`, release `1`.

### Construir desde el repositorio

Requiere Python **3.11+** para construir (la aplicación
instalada sigue necesitando Python 3.10+). Ejecuta:

```bash
python3 tools/package.py build --output dist/native
```

En Arch, con `base-devel`, Python y Git ya instalados:

```bash
python3 tools/package.py build --arch \
  --output dist/native-arch
```

No usa `makepkg --syncdeps` ni instala paquetes del SO.
Si falta una herramienta/dependencia, el proceso falla
conservando las salidas ya construidas. Usa siempre
un directorio de salida nuevo o vacío; no sobrescribe
una entrega anterior.

Se emiten:

- `pxp-harness_0.1.0-1_all.deb`.
- `pxp-harness-0.1.0-source.tar.gz`: fuente permitida,
  tests y herramientas necesarios para reconstruir.
- `pxp-harness-0.1.0-arch-build.tar.gz`: `PKGBUILD`
  utilizable y la misma fuente local, con SHA-256 real.
- `arch/PKGBUILD` y su fuente para ejecutar `makepkg`
  directamente sin descargar el proyecto.
- `manifest.json` y `SHA256SUMS` para verificar entrega.
- Con `--arch`, `pxp-harness-0.1.0-1-any.pkg.tar.zst`.

Los nombres cambian automáticamente con la versión.
Comprueba los archivos desde el directorio de salida:

```bash
sha256sum -c SHA256SUMS
```

Para usar la receta fuente Arch en otra máquina:

```bash
mkdir arch-build
cd arch-build
tar -xzf ../pxp-harness-0.1.0-arch-build.tar.gz
makepkg
```

La construcción parte de una lista explícita de fuentes:
no copia `.git/`, `.pxp/`, `.codex/`, entornos, cachés,
artefactos de otros proyectos ni prompts personales.
La skill se incluye como recurso estático, no se
registra globalmente en Codex.

### Instalar en la máquina de destino

Estos comandos requieren permisos de administrador y
**los ejecuta el usuario**, no el builder:

```bash
# Debian
sudo apt install ./pxp-harness_0.1.0-1_all.deb

# Arch
sudo pacman -U ./pxp-harness-0.1.0-1-any.pkg.tar.zst
```

En Arch, Git, NeoVim y Ruff son dependencias opcionales;
instala Git/NeoVim si vas a usar repositorios o edición.
Debian recomienda Git y NeoVim y sugiere Ruff. Ruff
0.16.4+ es necesario solo para `standards check/apply`.
Codex es un requisito externo para `chat`: instálalo
y autentícalo por separado con sus instrucciones
oficiales. Ningún paquete lo descarga ni inicia login.

Se instala un lanzador `/usr/bin/pxp` con Python del
sistema y módulos privados en `/usr/share/pxp-harness/`.
No contiene un venv ni modifica módulos de Python
ajenos. La documentación y el aviso de empaquetado
se guardan en rutas estándar bajo `/usr/share/`.
Debian compila/limpia exclusivamente el bytecode de
la aplicación al instalar o retirar el paquete.

### Configuración SIEMPRE por proyecto

Ni el paquete ni PXP escriben en
`~/.codex/config.toml`, `$CODEX_HOME/config.toml`,
perfiles de shell ni `.codex/config.toml` del proyecto.
Todos los archivos de base prompts y asociaciones
permanecen dentro del repo, en `.pxp/prompts.json`
y las rutas locales que elijas. Cada `pxp chat` pasa
el archivo del modo activo mediante `-c
model_instructions_file=...` solo a ese proceso.
`EDITOR`/`VISUAL` también se establecen únicamente en
el proceso hijo, no globalmente.

La suite prueba dos proyectos con prompts distintos y
un `CODEX_HOME/config.toml` centinela: `init`, ajustes,
edición y lanzamiento simulado conservan sus bytes.
Esto prueba lo que hace PXP; Codex puede mantener su
propio historial/autenticación al ejecutarse realmente.
Actualizar o retirar el paquete no borra tus repos ni
sus archivos `.pxp/`.

### Reproducibilidad, validación y límites

Los archivos Debian y los tarballs se normalizan por
orden, UID/GID 0, permisos y `SOURCE_DATE_EPOCH`.
Con la misma fuente, fecha y herramienta de construcción
se comprueban bytes idénticos. Puedes fijar la fecha:

```bash
SOURCE_DATE_EPOCH=1700000000 python3 tools/package.py \
  build --output dist/rebuild
```

Ese valor también es el predeterminado documentado;
no representa la fecha de publicación del proyecto.
Arch usa su flujo nativo y guarda `.BUILDINFO` con
versiones instaladas y rutas del entorno de build.
Para comparar bytes Arch necesitas también el mismo
entorno/rutas/configuración de makepkg. No se promete
reproducción bit a bit entre hosts distintos.

Se puede inspeccionar/extractar y probar el lanzador
sin instalar el paquete en el sistema. Una validación
por extracción no sustituye una instalación real en
una VM Debian/Arch limpia. No se ha creado una imagen
de VM, repositorio APT/Pacman, firma ni publicación AUR.

**Aviso de redistribución:** los metadatos originales
indican MIT, pero el proyecto no trae su aviso completo
de licencia/copyright. `packaging/NOTICE` registra esa
limitación sin inventar autoría ni conceder derechos.
El maintainer Debian predeterminado usa el dominio
reservado `example.invalid` para builds locales; usa
`--maintainer 'Nombre <correo-publico-verificado>'`
con datos reales solo si decides redistribuir y tras
resolver el aviso ausente.

Referencias técnicas:
[política Python Debian](https://www.debian.org/doc/packaging-manuals/python-policy/),
[formato Debian](https://manpages.debian.org/unstable/dpkg-dev/deb.5.en.html),
[PKGBUILD](https://man.archlinux.org/man/PKGBUILD.5.en).

## Desarrollo y verificación

```bash
ruff check .
ruff format --check .
PYTHONPATH=src python -m unittest discover -s tests -v
```

El repositorio configura Ruff a 50 columnas. La suite
comprueba también cada línea Python en `src/` y
`tests/`, sin excepciones por URL. La integración
continua repite lint, formato y pruebas con Python
3.10 y 3.14. Comprueba el resultado de CI: definir el
workflow no demuestra que se haya ejecutado.

Para refactorizar usa `ruff check --fix .` y
`ruff format .`, después repite las comprobaciones.
Las pruebas de lanzamiento de Codex usan simulaciones:
verifican argumentos y rutas, pero no prueban
la autenticación real, SSH ni Termux.

## Seguridad y terminal remota

PXP no usa `sudo`, no cambia propietarios ni permisos
y no proporciona servidor o TUI. Desde Termux puedes
conectarte por SSH a Debian, entrar en el proyecto y
usar la misma CLI. Nunca guardes claves, tokens ni
datos personales en los artefactos públicos. La
separación de usuarios UNIX queda fuera de este MVP.

## Diagnóstico de sandbox en VM

Antes de implementar permisos efectivos por rol,
ejecuta la [prueba local de sandbox](docs/sandbox-test.md).
No llama a modelos ni modifica configuración global.
Un resultado básico PASS no valida todavía perfiles
por rol ni protección de su política.
