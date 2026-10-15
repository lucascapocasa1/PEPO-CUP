"""Descarga cartas FUT de FUTBIN y las guarda en static/cartas/.

Formato del archivo de entrada (texto, una línea por jugador):
    mbappe|https://cdn.futbin.com/fc/27/playerimages/123.png
    (nombre del archivo)|(URL de la carta)

Uso: python manage.py bajar_cartas jugadores.txt

Nota: en PythonAnywhere free no hay internet saliente, así que este comando
se corre en tu computadora y después subís las imágenes con el deploy.
"""

import re
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

DESTINO = Path(settings.BASE_DIR) / 'static' / 'cartas'

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


class Command(BaseCommand):
    help = 'Descarga cartas FUT desde URLs (ej: de FUTBIN) a static/cartas/'

    def add_arguments(self, parser):
        parser.add_argument('archivo', help='Archivo con líneas: nombre_archivo|URL')

    def handle(self, *args, **options):
        origen = Path(options['archivo'])
        if not origen.exists():
            raise CommandError(f'No existe el archivo {origen}')

        DESTINO.mkdir(parents=True, exist_ok=True)
        lineas = [l.strip() for l in origen.read_text(encoding='utf-8').splitlines() if l.strip()]

        for linea in lineas:
            if '|' not in linea:
                self.stdout.write(self.style.WARNING(f'Salto (formato inválido): {linea}'))
                continue
            nombre_archivo, url = linea.split('|', 1)
            nombre_archivo = nombre_archivo.strip()
            url = url.strip()

            if not re.match(r'^[a-z0-9_\-.]+$', nombre_archivo):
                self.stdout.write(self.style.WARNING(f'Salto (nombre inválido): {nombre_archivo}'))
                continue

            extension = '.png' if '.png' in url.lower() else '.jpg' if '.jpg' in url.lower() else '.webp'
            destino = DESTINO / f'{nombre_archivo}{extension}'

            try:
                req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    destino.write_bytes(resp.read())
                self.stdout.write(self.style.SUCCESS(f'OK: {destino.name}'))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'ERROR con {url}: {exc}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nListo. Cartas en {DESTINO}. Acordate de commitear static/cartas/ a git.'
        ))
