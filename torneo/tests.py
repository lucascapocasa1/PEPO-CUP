from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import services
from .forms import EventoFormSet
from .models import EventoPartido, Partido, Participante, Torneo


def crear_torneo(nombres=('A', 'B', 'C', 'D', 'E')):
    torneo = Torneo.objects.create(nombre='Test Cup', slug='test-cup')
    for i, nombre in enumerate(nombres):
        p = Participante.objects.create(torneo=torneo, nombre=nombre, orden=i + 1)
        for j in range(11):
            p.jugadores.create(nombre=f'J{j} {nombre}', posicion='MED', rating=84, orden=j + 1)
    return torneo


class FixtureTests(TestCase):
    def test_fixture_ida_todos_contra_todos(self):
        torneo = crear_torneo()
        cantidad = services.generar_fixture_liga(torneo)

        # 5 participantes => 10 partidos en ida
        self.assertEqual(cantidad, 10)
        self.assertEqual(Partido.objects.filter(torneo=torneo).count(), 10)

    def test_fixture_sin_repetir_cruces(self):
        torneo = crear_torneo()
        services.generar_fixture_liga(torneo)
        cruces = {
            tuple(sorted([p.local.nombre, p.visitante.nombre]))
            for p in Partido.objects.filter(torneo=torneo)
        }
        self.assertEqual(len(cruces), 10)  # todos distintos

    def test_fixture_balancea_localias(self):
        torneo = crear_torneo()
        services.generar_fixture_liga(torneo)

        # Con 5 participantes cada uno juega 4 partidos: 2 de local, 2 de visitante
        for participante in torneo.participantes.all():
            locales = Partido.objects.filter(torneo=torneo, local=participante).count()
            visitantes = Partido.objects.filter(torneo=torneo, visitante=participante).count()
            self.assertEqual(locales, 2, f'{participante.nombre}: {locales} de local')
            self.assertEqual(visitantes, 2, f'{participante.nombre}: {visitantes} de visitante')


class TablaTests(TestCase):
    def test_tabla_calcula_puntos(self):
        torneo = crear_torneo()
        services.generar_fixture_liga(torneo)

        a, b = torneo.participantes.all()[:2]
        Partido.objects.create(
            torneo=torneo, local=a, visitante=b,
            goles_local=3, goles_visitante=1, jugado=True,
        )

        tabla = services.tabla_posiciones(torneo)
        fila_a = next(f for f in tabla if f['participante'] == a)
        fila_b = next(f for f in tabla if f['participante'] == b)

        self.assertEqual(fila_a['pts'], 3)
        self.assertEqual(fila_a['gf'], 3)
        self.assertEqual(fila_a['gc'], 1)
        self.assertEqual(fila_b['pts'], 0)
        self.assertEqual(tabla[0]['participante'], a)

    def test_empate_da_un_punto(self):
        torneo = crear_torneo()
        a, b = torneo.participantes.all()[:2]
        Partido.objects.create(
            torneo=torneo, local=a, visitante=b,
            goles_local=2, goles_visitante=2, jugado=True,
        )
        tabla = services.tabla_posiciones(torneo)
        self.assertEqual(tabla[0]['pts'], 1)
        self.assertEqual(tabla[1]['pts'], 1)


class GoleadoresTests(TestCase):
    def test_goleadores_y_asistencias(self):
        torneo = crear_torneo()
        a, b = torneo.participantes.all()[:2]
        partido = Partido.objects.create(
            torneo=torneo, local=a, visitante=b,
            goles_local=2, goles_visitante=0, jugado=True, figura=a.jugadores.first(),
        )
        EventoPartido.objects.create(partido=partido, jugador=a.jugadores.first(), tipo='gol')
        EventoPartido.objects.create(partido=partido, jugador=a.jugadores.first(), tipo='gol')
        EventoPartido.objects.create(partido=partido, jugador=a.jugadores.all()[1], tipo='asistencia')

        goleadores = services.tabla_goleadores(torneo)
        self.assertEqual(goleadores[0]['jugador'], a.jugadores.first())
        self.assertEqual(goleadores[0]['goles'], 2)
        self.assertEqual(goleadores[0]['figuras'], 1)


class CargarResultadoTests(TestCase):
    def setUp(self):
        self.torneo = crear_torneo()
        services.generar_fixture_liga(self.torneo)
        self.partido = Partido.objects.filter(torneo=self.torneo).first()
        self.user = get_user_model().objects.create_user(
            username='org', password='secret',
        )
        self.client.force_login(self.user)

    def test_cargar_resultado_con_eventos_y_figura(self):
        local_jugadores = list(self.partido.local.jugadores.all())
        visitante_jugadores = list(self.partido.visitante.jugadores.all())

        p = EventoFormSet(instance=self.partido).prefix  # 'eventos'
        datos = {
            'goles_local': 3,
            'goles_visitante': 1,
            'jugado': 'on',
            'figura': str(local_jugadores[0].pk),
            f'{p}-TOTAL_FORMS': '3',
            f'{p}-INITIAL_FORMS': '0',
            f'{p}-MIN_NUM_FORMS': '0',
            f'{p}-MAX_NUM_FORMS': '1000',
            f'{p}-0-jugador': str(local_jugadores[0].pk),
            f'{p}-0-tipo': 'gol',
            f'{p}-0-minuto': '10',
            f'{p}-1-jugador': str(local_jugadores[1].pk),
            f'{p}-1-tipo': 'asistencia',
            f'{p}-1-minuto': '10',
            f'{p}-2-jugador': str(visitante_jugadores[0].pk),
            f'{p}-2-tipo': 'gol',
            f'{p}-2-minuto': '88',
        }

        url = reverse('cargar_partido', args=[self.partido.pk])
        response = self.client.post(url, datos)
        if response.status_code != 302:
            form = response.context['resultado_form']
            formset = response.context['formset']
            self.fail(f'No guardó. form errors={form.errors} formset errors={formset.errors} non_form={formset.non_form_errors()}')

        partido = Partido.objects.get(pk=self.partido.pk)
        self.assertTrue(partido.jugado)
        self.assertEqual(partido.goles_local, 3)
        self.assertEqual(partido.goles_visitante, 1)
        self.assertEqual(partido.figura, local_jugadores[0])
        self.assertEqual(partido.eventos.count(), 3)
        self.assertEqual(partido.eventos.filter(tipo='gol').count(), 2)

    def test_reasignar_resultado_ya_cargado(self):
        """Re-guardar un partido que ya tiene resultado y eventos debe funcionar."""
        local_jugadores = list(self.partido.local.jugadores.all())
        visitante_jugadores = list(self.partido.visitante.jugadores.all())
        p = EventoFormSet(instance=self.partido).prefix

        def datos_enviados(totales, iniciales):
            """Armá el POST como lo manda el navegador."""
            datos = {
                'goles_local': 3,
                'goles_visitante': 1,
                'jugado': 'on',
                'figura': str(local_jugadores[0].pk),
                f'{p}-TOTAL_FORMS': str(totales),
                f'{p}-INITIAL_FORMS': str(iniciales),
                f'{p}-MIN_NUM_FORMS': '0',
                f'{p}-MAX_NUM_FORMS': '1000',
                f'{p}-0-jugador': str(local_jugadores[0].pk),
                f'{p}-0-tipo': 'gol',
                f'{p}-0-minuto': '10',
                f'{p}-1-jugador': str(local_jugadores[1].pk),
                f'{p}-1-tipo': 'asistencia',
                f'{p}-1-minuto': '10',
                f'{p}-2-jugador': str(visitante_jugadores[0].pk),
                f'{p}-2-tipo': 'gol',
                f'{p}-2-minuto': '88',
            }
            return datos

        url = reverse('cargar_partido', args=[self.partido.pk])

        # Primera carga: 3 formularios, ninguno inicial
        response = self.client.post(url, datos_enviados(3, 0))
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))

        # Re-guardar: ahora hay 3 formularios guardados (con su id oculto) y 6 extra en blanco
        segunda = datos_enviados(9, 3)
        eventos = list(self.partido.eventos.order_by('id'))
        for i in range(3):
            segunda[f'{p}-{i}-id'] = str(eventos[i].pk)
        for i in range(3, 9):
            segunda[f'{p}-{i}-jugador'] = ''
            segunda[f'{p}-{i}-tipo'] = ''
            segunda[f'{p}-{i}-minuto'] = ''
        response = self.client.post(url, segunda)
        if response.status_code != 302:
            formset = response.context['formset']
            self.fail(
                f'No re-guardó. form errors={response.context["resultado_form"].errors} '
                f'formset errors={formset.errors} non_form={formset.non_form_errors()}'
            )

        partido = Partido.objects.get(pk=self.partido.pk)
        self.assertEqual(partido.goles_local, 3)
        self.assertEqual(partido.eventos.count(), 3)  # no duplicó

    def test_cargar_requiere_login(self):
        self.client.logout()
        url = reverse('cargar_partido', args=[self.partido.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/entrar/', response.url)


class PlayoffsTests(TestCase):
    def test_generar_playoffs_y_final(self):
        torneo = crear_torneo(('A', 'B', 'C', 'D'))
        services.generar_fixture_liga(torneo)

        # Jugamos todos los partidos: gana siempre el de mejor seed (A primero)
        for partido in torneo.partidos.all():
            if partido.local.orden < partido.visitante.orden:
                partido.goles_local, partido.goles_visitante = 1, 0
            else:
                partido.goles_local, partido.goles_visitante = 0, 1
            partido.jugado = True
            partido.save()

        tabla = services.tabla_posiciones(torneo)
        self.assertEqual(tabla[0]['participante'].nombre, 'A')

        semis = services.generar_playoffs(torneo)
        self.assertEqual(len(semis), 2)
        torneo.refresh_from_db()
        self.assertEqual(torneo.estado, Torneo.ESTADO_PLAYOFFS)

        # Jugamos las semifinales con ganador
        for semi in semis:
            semi.goles_local = 2
            semi.goles_visitante = 1
            semi.jugado = True
            semi.save()

        final = services.avanzar_playoffs(torneo)
        self.assertIsNotNone(final)
        self.assertEqual(final.ronda, 'Final')
        # No se crea otra final
        self.assertIsNone(services.avanzar_playoffs(torneo))

    def test_ganador_por_penales(self):
        torneo = crear_torneo()
        a, b = torneo.participantes.all()[:2]
        partido = Partido.objects.create(
            torneo=torneo, fase=Partido.FASE_PLAYOFF, ronda='Final',
            local=a, visitante=b,
            goles_local=1, goles_visitante=1,
            penales_local=5, penales_visitante=4,
            jugado=True,
        )
        self.assertEqual(partido.ganador, a)
