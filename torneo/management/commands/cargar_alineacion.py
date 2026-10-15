"""Carga la alineación FUT de un participante desde un archivo de texto.

Formato del archivo (una línea por jugador):
    Nombre|Posición|Rating|archivo_de_carta

Posiciones: POR, DEF, MED, DEL (la carta del juego usa GK/DEF/MID/FWD,
pero acá las normalizamos a esas cuatro).

Los primeros 11 son titulares. Para marcar suplentes, poné una línea
que diga exactamente: suplentes

Ejemplo:
    Joan Garcia|POR|86|joangarcia.png
    Xavi Espart|DEF|85|espart.png
    ...
    Chawinga|DEL|87|chawinga.png
    suplentes
    Suplente Uno|MED|83|suplente1.png

Líneas vacías y las que empiezan con # se ignoran.

Uso:
    python manage.py cargar_alineacion lucas alineaciones/lucas.txt --formacion 4-2-3-1
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from torneo.models import JugadorFUT, Participante, Torneo

POSICIONES = {'POR', 'DEF', 'MED', 'DEL'}
POSICIONES_JUEGO = {
    'GK': 'POR', 'POR': 'POR',
    'DEF': 'DEF', 'CB': 'DEF', 'LB': 'DEF', 'RB': 'DEF', 'RWB': 'DEF', 'LWB': 'DEF',
    'MED': 'MED', 'CDM': 'MED', 'CM': 'MED', 'CAM': 'MED', 'RM': 'MED', 'LM': 'MED',
    'DEL': 'DEL', 'ST': 'DEL', 'CF': 'DEL', 'LW': 'DEL', 'RW': 'DEL',
}


class Command(BaseCommand):
    help = 'Carga (o reemplaza) la alineación FUT de un participante desde un archivo'

    def add_arguments(self, parser):
        parser.add_argument('participante', help='Nombre del participante, ej: lucas')
        parser.add_argument('archivo', help='Archivo con la alineación')
        parser.add_argument('--formacion', default=None, help='Ej: 4-2-3-1')
        parser.add_argument('--torneo', default=None, help='Slug del torneo (si hay más de uno)')

    def handle(self, *args, **options):
        ruta = Path(options['archivo'])
        if not ruta.exists():
            raise CommandError(f'No existe el archivo {ruta}')

        torneo = (
            Torneo.objects.get(slug=options['torneo']) if options['torneo']
            else Torneo.objects.order_by('-creado').first()
        )
        if torneo is None:
            raise CommandError('No hay torneos cargados.')

        nombre = options['participante']
        participante = (
            Participante.objects.filter(torneo=torneo, nombre__iexact=nombre).first()
            or Participante.objects.filter(torneo=torneo, apodo__iexact=nombre).first()
        )
        if participante is None:
            disponibles = ', '.join(torneo.participantes.values_list('nombre', flat=True))
            raise CommandError(f'No encontré a "{nombre}". Disponibles: {disponibles}')

        jugadores = []
        titulares = True
        for numero, linea in enumerate(ruta.read_text(encoding='utf-8').splitlines(), start=1):
            linea = linea.strip()
            if not linea or linea.startswith('#'):
                continue
            if linea.lower() in ('suplentes', '---'):
                titulares = False
                continue

            partes = [p.strip() for p in linea.split('|')]
            if len(partes) < 3:
                raise CommandError(
                    f'Línea {numero} inválida: "{linea}". '
                    f'Formato: Nombre|Posición|Rating|carta'
                )

            jugador_nombre, posicion, rating = partes[0], partes[1].upper(), partes[2]
            carta = partes[3] if len(partes) > 3 else ''

            posicion = POSICIONES_JUEGO.get(posicion, posicion)
            if posicion not in POSICIONES:
                raise CommandError(
                    f'Línea {numero}: posición "{partes[1]}" inválida. '
                    f'Usá POR, DEF, MED o DEL (o las del juego: GK, CB, CDM, CAM, ST...)'
                )
            try:
                rating = int(rating)
            except ValueError:
                raise CommandError(f'Línea {numero}: el rating "{partes[2]}" no es un número.')

            jugadores.append({
                'nombre': jugador_nombre,
                'posicion': posicion,
                'rating': rating,
                'carta': carta,
                'titular': titulares,
            })

        if not jugadores:
            raise CommandError('El archivo no tiene jugadores.')

        titulares_total = sum(1 for j in jugadores if j['titular'])
        if titulares_total != 11:
            self.stdout.write(self.style.WARNING(
                f'Ojo: hay {titulares_total} titulares (lo normal es 11). Igual cargo igual.'
            ))

        participante.jugadores.all().delete()
        for i, jugador in enumerate(jugadores):
            JugadorFUT.objects.create(
                participante=participante,
                nombre=jugador['nombre'],
                posicion=jugador['posicion'],
                rating=jugador['rating'],
                carta=jugador['carta'],
                titular=jugador['titular'],
                orden=i + 1,
            )

        if options['formacion']:
            participante.formacion = options['formacion']
            participante.save(update_fields=['formacion'])

        self.stdout.write(self.style.SUCCESS(
            f'Alineación de {participante.nombre} cargada: '
            f'{titulares_total} titulares y {len(jugadores) - titulares_total} suplentes.'
            + (f' Formación {participante.formacion}.' if options['formacion'] else '')
        ))
