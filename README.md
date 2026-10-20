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

## Iniciar con instrucciones base propias

Para sustituir las instrucciones base incorporadas de
Codex en un modo, crea primero tu propio archivo UTF-8
en el proyecto. PXP no genera su contenido ni exige
que los nueve modos tengan uno.

```bash
pxp init
# Crea y revisa prompts/plan.md con tu editor.
pxp prompt set plan prompts/plan.md
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
