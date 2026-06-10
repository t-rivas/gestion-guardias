# Guía de instalación

## Requisitos

- Python 3.12
- Docker y Docker Compose
- Git

## 1. Clonar el repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd gestion-guardias
```

## 2. Configurar variables de entorno

Copiar el archivo de ejemplo:

```bash
cp .env.example .env
```

La configuración predeterminada conecta la aplicación con PostgreSQL en:

```text
host: localhost
port: 5433
database: guardias
user: guardias
password: guardias
```

Variables disponibles:

| Variable | Descripción | Valor predeterminado |
| --- | --- | --- |
| `DATABASE_URL` | URL de conexión de SQLAlchemy | `postgresql+psycopg://guardias:guardias@localhost:5433/guardias` |
| `SQLALCHEMY_ECHO` | Muestra consultas SQL en consola | `false` |

La aplicación funciona con los valores predeterminados incluso si no se carga `.env`. Para usar los valores del archivo en la terminal:

```bash
set -a
source .env
set +a
```

## 3. Iniciar PostgreSQL

```bash
docker compose up -d db
```

Comprobar el estado:

```bash
docker compose ps
```

## 4. Crear el entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

En Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

## 5. Instalar dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 6. Ejecutar la aplicación

```bash
uvicorn app.main:app --reload --port 8001
```

Abrir:

```text
http://localhost:8001
```

Las tablas se crean automáticamente al iniciar la aplicación. En instalaciones existentes, el inicio también aplica la actualización necesaria sobre `guard_assignments` para soportar múltiples asignaciones diarias con rol y posición.

## Actualizar una instalación existente

1. Descargar la última versión del repositorio.
2. Instalar dependencias si `requirements.txt` cambió.
3. Iniciar la aplicación normalmente.

Al iniciar, la aplicación agrega las columnas `role` y `slot` a `guard_assignments`, elimina la restricción antigua de una sola asignación por fecha y crea las nuevas restricciones de unicidad por fecha/posición y fecha/persona.

## Detener los servicios

Detener PostgreSQL sin borrar los datos:

```bash
docker compose down
```

Detener PostgreSQL y borrar el volumen de datos:

```bash
docker compose down -v
```

## Solución de problemas

### El puerto 5433 está ocupado

Modificar el puerto publicado en `docker-compose.yml` y actualizar `DATABASE_URL`.

### La aplicación no conecta con PostgreSQL

Verificar que el contenedor esté activo:

```bash
docker compose ps
docker compose logs db
```

### Cambios de modelos no aparecen en tablas existentes

El proyecto no utiliza Alembic. `Base.metadata.create_all()` crea tablas faltantes, pero no modifica columnas existentes. La tabla `guard_assignments` tiene una actualización puntual al iniciar la aplicación; para futuros cambios de esquema se recomienda incorporar Alembic.
