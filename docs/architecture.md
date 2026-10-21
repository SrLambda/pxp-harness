# Extender modos, agentes y herramientas

PXP conserva los nueve modos originales si no existe
`workflow` en `.pxp/config.json`. Los prompts, estándares,
memoria y MCP siguen siendo configuración del proyecto.
No se escriben ajustes globales de Codex.

## Crear un flujo distinto de PXP

Edita `.pxp/config.json` con NeoVim. Ejemplo completo
para un flujo de entrega con dos modos y un artefacto:

```json
{
  "schema_version": 1,
  "active_mode": "review",
  "artifacts": {"brief": "brief.md"},
  "workflow": {
    "id": "delivery",
    "modes": [
      {
        "id": "review",
        "label": "Delivery review",
        "group": "delivery",
        "artifacts": ["brief"]
      },
      {
        "id": "ship",
        "label": "Delivery preparation",
        "group": "delivery",
        "artifacts": ["brief"]
      }
    ]
  }
}
```

Ejecuta `pxp init` para crear los artefactos que falten,
sin sobrescribir archivos existentes. `pxp mode` lista
los modos declarados; `pxp mode ship` cambia el activo.
`pxp prompt edit ship` permite asociar su base propia.
Un catálogo `artifacts: {}` es válido para un flujo
personalizado cuyos modos tengan `artifacts: []`.

Los IDs empiezan por letra minúscula y admiten letras
minúsculas, dígitos, `_` y `-`, hasta 64 caracteres.
Los modos deben ser únicos y referenciar claves del
catálogo. Se rechazan campos desconocidos, tipos
incorrectos y rutas de artefactos fuera del proyecto.
Las rutas son relativas a `.pxp/artifacts/`.
El campo opcional `backend` solo admite `codex` por ahora.

Al retirar un modo no se borran sus archivos.
`pxp prompt clear <id-retirado>` quita su asociación
sin borrar el archivo ni bloquear los modos vigentes.
Los prompts conservan su asociación por ID de modo dentro
del proyecto; revisa esas asociaciones si reutilizas
un ID con otro significado. Los bindings MCP además
se separan por ID de workflow para evitar que un flujo
nuevo herede herramientas por coincidencia de modo.

## Añadir un MCP a un modo

Instala y verifica el servidor por separado. PXP no
descarga programas ni ejecuta una shell de instalación.
Usa una ruta absoluta a un ejecutable confiable:

```sh
pxp mcp add review docs \
  --command /ruta/al/servidor \
  --arg=--stdio --env-var DOCS_TOKEN
pxp mcp list review
pxp mcp remove review docs
```

Cada `--arg` añade un argumento literal. Usa `--arg=...`
si empieza por `-`; las rutas con espacios van entre
comillas. `--env-var` guarda solo el NOMBRE de una
variable disponible en el entorno de Codex, nunca su
valor. No pongas tokens en argumentos ni en el JSON:
PXP no detecta automáticamente secretos dentro de texto.
Sin modo, `list` muestra el activo. Cambios aplican al
próximo `pxp chat`, no a sesiones abiertas.

`.pxp/mcps.json` contiene un esquema versionado con
`workflows -> <workflow> -> <mode> -> <server>` y los
campos `command`, `args`, `env_vars`. No admite valores
`env` en declaraciones públicas. El comando debe existir
y ser ejecutable al añadirlo y al lanzar Codex.
Retirar un binding no desinstala ni elimina datos del
servidor. Guarda únicamente configuraciones revisadas;
un MCP es código con capacidades REALES, no solo texto.

PXP selecciona sus MCP por modo y pasa opciones nativas
`-c` efímeras a Codex. Esto **no desactiva ni aísla los
MCP globales heredados**. Tampoco implementa permisos
por rol ni evita que un ejecutable confiado haga daño.
La memoria integrada reutiliza la misma especificación
MCP; con memoria activa, reserva el nombre `engram`.
No añadas otro binding con ese nombre: se rechaza la
colisión antes de iniciar Codex.

## Contratos de extensión en Python

- `ModeBuilder(id).build(label, group, artifacts)`
  valida y publica un `Mode` inmutable.
- `Workflow(id, tuple_of_modes)` valida la colección.
  No carga plugins Python desde configuración.
- `LaunchRequest` contiene contexto, solicitud de
  usuario, archivo base, servidores y notas, sin argv
  específicos de un proveedor.
- `AgentStrategy.launch(request)` es el punto de
  extensión. `main(..., strategy=fake)` permite probar
  otro adaptador sin ejecutar Codex. Añadir un backend
  público requiere validación explícita: un nombre
  desconocido en JSON falla antes de lanzar procesos.
- `CodexStrategy` concentra serialización TOML, argv,
  entorno hijo y lanzamiento de la TUI nativa. La base
  usa `model_instructions_file`; la solicitud no se
  incorpora a ese archivo. El protocolo de memoria usa
  notas adicionales, no reemplaza el prompt propio.
- `AddMCP.execute(root)` y `RemoveMCP.execute(root)`
  comparten IO local y no necesitan un framework de undo.

## Escrituras y límites

La capa `localio` rechaza rutas simbólicas y ancestros
simbólicos antes de los efectos de inicialización.
Valida JSON sin mostrar su contenido en errores.
Los cambios de configuración usan archivo temporal y
reemplazo atómico: no truncan un archivo enlazado por
hardlink en otro proyecto. Un fallo de validación no
repara ni borra datos automáticamente.

Esto NO es una frontera contra carreras de otro proceso
con el mismo UID ni un sandbox del editor, Codex o MCP.
No hace inmutables la política ni los prompts frente
a esos procesos. La protección efectiva por rol sigue
pendiente; no se promete aislamiento que no existe.

Referencias: [MCP de Codex](https://learn.chatgpt.com/docs/extend/mcp)
y [configuración nativa](https://learn.chatgpt.com/docs/config-file/config-reference).
