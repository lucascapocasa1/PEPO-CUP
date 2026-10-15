"""Crea un torneo de prueba con 8 participantes y sus alineaciones.

Uso: python manage.py crear_demo
"""

from django.core.management.base import BaseCommand

from torneo import services
from torneo.models import JugadorFUT, Participante, Torneo

# Formación típica: POR, 4 DEF, 3-4 MED, 2-3 DEL
PLANTILLA = [
    ('POR', 'Arquero'),
    ('DEF', 'Defensor 1'), ('DEF', 'Defensor 2'), ('DEF', 'Defensor 3'), ('DEF', 'Defensor 4'),
    ('MED', 'Mediocampista 1'), ('MED', 'Mediocampista 2'), ('MED', 'Mediocampista 3'),
    ('DEL', 'Delantero 1'), ('DEL', 'Delantero 2'), ('DEL', 'Delantero 3'),
]

NOMBRES = [
    'Capo', 'Tomi', 'Nico', 'Fede', 'Lucho', 'Mati', 'Santi', 'Juli',
]


class Command(BaseCommand):
    help = 'Crea un torneo de prueba con 8 participantes (para probar la página)'

    def handle(self, *args, **options):
        if Torneo.objects.filter(slug='demo').exists():
            self.stdout.write(self.style.WARNING('El torneo demo ya existe. Borrá la base o usá otro slug.'))
            return

        torneo = Torneo.objects.create(
            nombre='PEPO CUP Demo',
            slug='demo',
            estado=Torneo.ESTADO_LIGA,
        )

        for i, nombre in enumerate(NOMBRES):
            participante = Participante.objects.create(
                torneo=torneo,
                nombre=nombre,
                club=f'FC {nombre}',
                formacion='4-3-1-2',
                orden=i + 1,
            )
            for j, (posicion, posicion_nombre) in enumerate(PLANTILLA):
                JugadorFUT.objects.create(
                    participante=participante,
                    nombre=f'{posicion_nombre} {nombre}',
                    posicion=posicion,
                    rating=80 + (j % 12),
                    titular=True,
                    orden=j + 1,
                )

        cantidad = services.generar_fixture_liga(torneo)
        self.stdout.write(self.style.SUCCESS(
            f'Torneo demo creado: {len(NOMBRES)} participantes, {cantidad} partidos de liga.\n'
            f'Entrá a / para verlo.'
        ))
