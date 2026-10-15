"""Crea un torneo con sus participantes y genera el fixture de liga.

Uso:
    python manage.py crear_torneo "PEPO CUP 2026" pepo-cup-2026 lucas santi valen ...

Con número impar de participantes, en cada fecha uno descansa.
"""

from django.core.management.base import BaseCommand, CommandError

from torneo import services
from torneo.models import Participante, Torneo


class Command(BaseCommand):
    help = 'Crea un torneo con sus participantes y arma el fixture de liga'

    def add_arguments(self, parser):
        parser.add_argument('nombre', help='Nombre del torneo, ej: "PEPO CUP 2026"')
        parser.add_argument('slug', help='Identificador corto, ej: pepo-cup-2026')
        parser.add_argument('jugadores', nargs='+', help='Nombres de los participantes')

    def handle(self, *args, **options):
        nombre = options['nombre']
        slug = options['slug']
        jugadores = options['jugadores']

        if Torneo.objects.filter(slug=slug).exists():
            raise CommandError(f'Ya existe un torneo con el slug "{slug}".')

        if len(jugadores) < 2:
            raise CommandError('Hacen falta al menos 2 participantes.')

        torneo = Torneo.objects.create(nombre=nombre, slug=slug)

        for i, jugador in enumerate(jugadores):
            Participante.objects.create(
                torneo=torneo,
                nombre=jugador.strip().title(),
                orden=i + 1,
            )

        cantidad = services.generar_fixture_liga(torneo)
        self.stdout.write(self.style.SUCCESS(
            f'{torneo.nombre} creado con {len(jugadores)} participantes '
            f'y {cantidad} partidos de liga.'
        ))
