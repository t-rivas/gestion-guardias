# Descripción del sistema

## Propósito

Gestión de Guardias es una aplicación interna para organizar guardias mensuales. Permite mantener el equipo, registrar excepciones de disponibilidad y generar una distribución automática de asignaciones.

La interfaz utiliza una identidad visual inspirada en BPS, navegación lateral, modo claro y modo nocturno persistente.

## Módulos

### Inicio

Ruta: `/`

Panel de acceso a Personas, Disponibilidad y Calendario.

### Personas

Ruta: `/personas`

Funciones:

- Crear personas con nombre y observaciones.
- Ordenar el listado alfabéticamente de A-Z o Z-A.
- Activar y desactivar personas.
- Eliminar personas de forma permanente.

Las personas inactivas se conservan en el historial, pero no participan en nuevas asignaciones. La eliminación también borra su disponibilidad y sus guardias asignadas.

### Disponibilidad

Ruta: `/disponibilidad`

La grilla mensual permite marcar disponibilidad por persona y día.

Reglas:

- De lunes a viernes, las personas están disponibles por defecto.
- Sábados y domingos, las personas están no disponibles por defecto.
- Un fin de semana se habilita haciendo clic en la celda correspondiente.
- Los cambios se mantienen como borrador en el navegador hasta presionar **Guardar cambios**.
- Solo se guardan excepciones a los valores predeterminados.

Tipos de excepción almacenados:

- `OTHER`: persona no disponible en un día de semana.
- `WEEKEND_AVAILABLE`: persona disponible en un sábado o domingo.

### Calendario

Ruta: `/calendario`

Genera y muestra las guardias del mes seleccionado.

Reglas actuales del generador:

1. Solo considera personas activas.
2. No asigna personas no disponibles.
3. No asigna fines de semana salvo que exista una habilitación explícita.
4. Intenta evitar asignaciones en días consecutivos.
5. Prioriza personas con menos guardias dentro del mes generado.
6. Selecciona aleatoriamente entre candidatos con la misma cantidad de guardias.
7. Mantiene una sola asignación por fecha.
8. Al regenerar, reemplaza únicamente las asignaciones del mes seleccionado.
9. Informa días sin candidatos y conflictos por cambios posteriores de disponibilidad o estado.

## Modelo de datos

### `people`

| Campo | Descripción |
| --- | --- |
| `id` | Identificador de la persona |
| `full_name` | Nombre completo |
| `active` | Indica si participa en nuevas asignaciones |
| `notes` | Observaciones opcionales |

### `availability`

| Campo | Descripción |
| --- | --- |
| `id` | Identificador de la excepción |
| `person_id` | Persona relacionada |
| `date` | Fecha de la excepción |
| `type` | Tipo de excepción de disponibilidad |

### `guard_assignments`

| Campo | Descripción |
| --- | --- |
| `id` | Identificador de la asignación |
| `person_id` | Persona asignada |
| `date` | Fecha de la guardia, única en la tabla |

## Arquitectura

```text
app/
├── api/          # Rutas FastAPI y renderizado de páginas
├── db/           # Base declarativa, engine y sesiones
├── models/       # Modelos SQLAlchemy
├── services/     # Reglas de disponibilidad y generador
├── static/       # CSS y JavaScript
├── templates/    # Plantillas Jinja2
└── main.py       # Configuración principal de FastAPI
```

## Límites actuales

- No existe autenticación ni control de permisos.
- No se consideran feriados.
- No existe edición manual de asignaciones.
- No se utilizan migraciones de base de datos.
- La aplicación está pensada para uso interno y una única organización.
