# PEPO CUP

Página del torneo entre amigos: tabla de posiciones, resultados con goles y asistencias, figura del partido, y página de cada participante con su alineación FUT.

**Stack:** Django + SQLite + templates (sin frameworks de frontend).

---

## Correr en tu máquina

```bash
python -m venv .venv
.venv\Scripts\activate        # en Windows; en Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py crear_demo   # torneo de prueba (opcional)
python manage.py runserver
```

Abrí http://127.0.0.1:8000/

Crear tu usuario de organizador:

```bash
python manage.py createsuperuser
```

---

## Cómo cargar los datos

Hay dos caminos, los dos andan desde el celular:

1. **`/cargar/`** — para resultados. Elegís el partido, ponés el marcador, agregás goles/asistencias y la figura. Es lo que vas a usar el 90% de las veces.
2. **`/admin/`** — para todo lo demás: crear torneos, participantes, alineaciones (con las cartas), generar el fixture y los playoffs.

### Flujo de un torneo

1. En el admin: creá el **Torneo** (nombre + slug, ej: `pepo-cup-2026`).
2. Agregá los **Participantes** (nombre, club, formación).
3. Dentro de cada participante, cargá sus **Jugadores FUT** (nombre, posición, rating, y el archivo de la carta en `static/cartas/`).
4. En el admin, entrá al torneo y ejecutá la acción **"Generar fixture de liga"**. Te arma todos los cruces (ida, todos contra todos).
5. A medida que se juegan, cargá los resultados en `/cargar/`.
6. Cuando termina la liga, acción **"Generar playoffs"** (semifinales: 1° vs 4° y 2° vs 3°).
7. Cargá las semifinales. Cuando ambas tienen ganador, la **Final se crea sola**. Cargala y listo: queda el campeón en la portada.

---

## Las cartas FUT

Las cartas son imágenes en `static/cartas/`. Hay un script que las baja de FUTBIN de una:

```bash
python manage.py bajar_cartas jugadores.txt
```

Donde `jugadores.txt` tiene una línea por jugador:

```
mbappe|https://cdn.futbin.com/fc/27/playerimages/123.png
haaland|https://cdn.futbin.com/fc/27/playerimages/456.jpg
```

(El nombre de la izquierda es el archivo final: `mbappe.png`. Después, en la ficha del jugador del admin, ponés ese nombre en el campo "Carta".)

Si FUTBIN no deja bajar, sacá la captura de la carta del juego y dejala con ese nombre en la carpeta.

---

## Deploy en PythonAnywhere (gratis)

Cuenta free: siempre encendida, sin cold start, sin tarjeta.

### 1. Crear la cuenta y la app

1. Registrate en https://www.pythonanywhere.com (plan **Beginner**, gratis).
2. **Web** → **Create a new web app** → elegí **Manual configuration** y la versión de Python que te ofrezca (3.12 o 3.13).
3. En la configuración de la app, anotá la ruta que te asigna (algo así como `/home/tuusuario/PEPOCUP`).

### 2. Subir el código

Lo más fácil: crear el repo en GitHub y clonarlo desde la consola de PythonAnywhere.

1. Subí este proyecto a GitHub (los archivos del repo ya están con `.gitignore`).
2. En PythonAnywhere: **Consoles** → abrí una consola Bash.
3. Cloná el repo en la carpeta de la app:

```bash
cd ~
git clone https://github.com/usuario/pepocup.git PEPOCUP
cd PEPOCUP
python3.12 -m venv ~/.virtualenvs/pepocup
source ~/.virtualenvs/pepocup/bin/activate
pip install -r requirements.txt
```

(Reemplazá `python3.12` por la versión de tu app, y el token de GitHub si el repo es privado.)

### 3. Base de datos y usuario

```bash
python manage.py migrate
python manage.py createsuperuser
```

La base (`db.sqlite3`) queda en tu carpeta y **persiste** en PythonAnywhere.

### 4. Estáticos

```bash
python manage.py collectstatic --noinput
```

### 5. Configurar la web app

En **Web** → en **Static files** agregá un mapeo:

| URL | Ruta |
|---|---|
| `/static/` | `/home/tuusuario/PEPOCUP/staticfiles` |

En **Code** → **WSGI configuration file** (el archivo `.wsgi.py`), reemplazá el contenido por:

```python
import os
import sys

project_home = os.path.expanduser('~/PEPOCUP')
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pepocup.settings')
os.environ.setdefault('DJANGO_DEBUG', '0')
os.environ.setdefault('DJANGO_ALLOWED_HOSTS', 'tuusuario.pythonanywhere.com')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Guardá y tocá **Reload**. Entrá a `https://tuusuario.pythonanywhere.com/` y listo.

### 6. Deploy de cambios

Cada vez que cambies algo:

```bash
bash ~/PEPOCUP/deploy.sh
```

O si preferís, entrá a la consela y corré los comandos a mano (`git pull`, `migrate`, `collectstatic`, y **Reload** en la pestaña Web).

---

## Seguridad

- El `/admin/` y `/cargar/` requieren login (tu usuario de organizador).
- Para producción, generá una clave secreta propia y seteala como variable de entorno `DJANGO_SECRET_KEY` en el archivo `.wsgi.py`:

```python
os.environ.setdefault('DJANGO_SECRET_KEY', 'una-clave-larga-y-rara')
```

- El archivo `db.sqlite3` está en el `.gitignore` para que no se suba a GitHub.
