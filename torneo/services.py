"""Lógica del torneo: fixture de liga, tabla de posiciones y playoffs."""

from collections import defaultdict

from django.db import transaction

from .models import EventoPartido, Partido, Participante


# ---------------------------------------------------------------------------
# Fixture de liga (todos contra todos, solo ida)
# ---------------------------------------------------------------------------

def generar_fixture_liga(torneo):
    """Genera el fixture de la liga (round-robin, ida). Borra la liga previa.

    Devuelve la cantidad de partidos creados. Se usa el método del círculo,
    así cada participante queda con la misma cantidad de fechas.
    """
    participantes = list(torneo.participantes.filter(activo=True).order_by('orden', 'nombre'))
    if len(participantes) < 2:
        return 0

    torneo.partidos.filter(fase=Partido.FASE_LIGA).delete()

    # Si hay número imparo, el que queda libre descansa esa fecha
    jugadores = participantes[:]
    if len(jugadores) % 2 == 1:
        jugadores.append(None)

    n = len(jugadores)
    fechas = n - 1
    partidos_creados = 0

    with transaction.atomic():
        for fecha in range(fechas):
            ronda = f'Fecha {fecha + 1}'
            # En fechas alternas se invierten local y visitante, para que
            # nadie quede siempre de local (o siempre de visitante).
            invertir = fecha % 2 == 1
            for i in range(n // 2):
                local = jugadores[i]
                visitante = jugadores[n - 1 - i]
                if local is None or visitante is None:
                    continue
                if invertir:
                    local, visitante = visitante, local
                Partido.objects.create(
                    torneo=torneo,
                    fase=Partido.FASE_LIGA,
                    ronda=ronda,
                    local=local,
                    visitante=visitante,
                )
                partidos_creados += 1
            # Rotación: el primer elemento fijo, el resto gira
            jugadores = [jugadores[0]] + [jugadores[-1]] + jugadores[1:-1]

    _balancear_localias(torneo)
    return partidos_creados


def _balancear_localias(torneo):
    """Ajusta local/visitante para que nadie quede con muchas más localías.

    El método del círulo no balancea perfecto con número impar de
    participantes, así que hacemos un par de pasadas corrigiendo.
    """
    partidos = list(Partido.objects.filter(torneo=torneo, fase=Partido.FASE_LIGA))
    locales = defaultdict(int)
    for partido in partidos:
        locales[partido.local_id] += 1

    for _ in range(3):
        hubo_cambios = False
        for partido in partidos:
            if locales[partido.local_id] - locales[partido.visitante_id] > 1:
                locales[partido.local_id] -= 1
                locales[partido.visitante_id] += 1
                partido.local, partido.visitante = partido.visitante, partido.local
                partido.save(update_fields=['local', 'visitante'])
                hubo_cambios = True
        if not hubo_cambios:
            break


# ---------------------------------------------------------------------------
# Tabla de posiciones (siempre calculada, nunca guardada)
# ---------------------------------------------------------------------------

def tabla_posiciones(torneo, fase=Partido.FASE_LIGA):
    """Devuelve la tabla de posiciones ordenada.

    Cada fila: dict con 'participante' y las stats PJ, G, E, P, GF, GC, DG, PTS.
    """
    participantes = torneo.participantes.filter(activo=True)
    stats = defaultdict(lambda: {
        'pj': 0, 'g': 0, 'e': 0, 'p': 0, 'gf': 0, 'gc': 0, 'dg': 0, 'pts': 0,
    })

    partidos = torneo.partidos.filter(fase=fase, jugado=True)
    for partido in partidos:
        if partido.goles_local is None or partido.goles_visitante is None:
            continue
        local, visitante = partido.local, partido.visitante
        gl, gv = partido.goles_local, partido.goles_visitante

        stats[local]['pj'] += 1
        stats[visitante]['pj'] += 1
        stats[local]['gf'] += gl
        stats[local]['gc'] += gv
        stats[visitante]['gf'] += gv
        stats[visitante]['gc'] += gl

        if gl > gv:
            stats[local]['g'] += 1
            stats[local]['pts'] += 3
            stats[visitante]['p'] += 1
        elif gv > gl:
            stats[visitante]['g'] += 1
            stats[visitante]['pts'] += 3
            stats[local]['p'] += 1
        else:
            stats[local]['e'] += 1
            stats[visitante]['e'] += 1
            stats[local]['pts'] += 1
            stats[visitante]['pts'] += 1

    filas = []
    for participante in participantes:
        s = dict(stats[participante])
        s['dg'] = s['gf'] - s['gc']
        s['participante'] = participante
        filas.append(s)

    # Orden: puntos, diferencia de gol, goles a favor, nombre
    filas.sort(key=lambda f: (-f['pts'], -f['dg'], -f['gf'], f['participante'].orden, f['participante'].nombre))
    return filas


def stats_participante(participante):
    """Stats individuales de un participante (liga + playoffs + goles de sus jugadores)."""
    torneo = participante.torneo
    tabla = tabla_posiciones(torneo)
    fila = next((f for f in tabla if f['participante'].pk == participante.pk), None)
    if fila is None:
        fila = {'pj': 0, 'g': 0, 'e': 0, 'p': 0, 'gf': 0, 'gc': 0, 'dg': 0, 'pts': 0}

    goles = EventoPartido.objects.filter(
        jugador__participante=participante, tipo=EventoPartido.TIPO_GOL,
    ).count()
    autogoles = EventoPartido.objects.filter(
        jugador__participante=participante, tipo=EventoPartido.TIPO_AUTOGOL,
    ).count()
    asistencias = EventoPartido.objects.filter(
        jugador__participante=participante, tipo=EventoPartido.TIPO_ASISTENCIA,
    ).count()
    figuras = Partido.objects.filter(figura__participante=participante).count()

    return {
        **fila,
        'goles': goles,
        'autogoles': autogoles,
        'asistencias': asistencias,
        'figuras': figuras,
    }


def tabla_goleadores(torneo, limite=None):
    """Ranking de goleadores (jugadores FUT) del torneo."""
    goleadores = defaultdict(lambda: {'goles': 0, 'asistencias': 0, 'figuras': 0})

    for evento in EventoPartido.objects.filter(
        partido__torneo=torneo, tipo=EventoPartido.TIPO_GOL,
    ).select_related('jugador'):
        goleadores[evento.jugador]['goles'] += 1

    for evento in EventoPartido.objects.filter(
        partido__torneo=torneo, tipo=EventoPartido.TIPO_ASISTENCIA,
    ).select_related('jugador'):
        goleadores[evento.jugador]['asistencias'] += 1

    for partido in Partido.objects.filter(torneo=torneo, figura__isnull=False).select_related('figura'):
        goleadores[partido.figura]['figuras'] += 1

    filas = []
    for jugador, stats in goleadores.items():
        filas.append({'jugador': jugador, **stats})

    filas.sort(key=lambda f: (-f['goles'], -f['asistencias'], f['jugador'].nombre))
    if limite:
        filas = filas[:limite]
    return filas


# ---------------------------------------------------------------------------
# Playoffs
# ---------------------------------------------------------------------------

PLAYOFF_CANTIDAD = 4  # semifinales entre los 4 primeros


def generar_playoffs(torneo, cantidad=PLAYOFF_CANTIDAD):
    """Crea las semifinales a partir de la tabla de la liga (1° vs 4°, 2° vs 3°).

    Devuelve los partidos creados, o None si faltan datos.
    """
    tabla = tabla_posiciones(torneo)
    if len(tabla) < cantidad:
        return None

    torneo.partidos.filter(fase=Partido.FASE_PLAYOFF, ronda='Semifinal').delete()
    top = [f['participante'] for f in tabla[:cantidad]]

    cruces = [
        (top[0], top[3]),  # 1° vs 4°
        (top[1], top[2]),  # 2° vs 3°
    ]

    creados = []
    with transaction.atomic():
        for local, visitante in cruces:
            creados.append(Partido.objects.create(
                torneo=torneo,
                fase=Partido.FASE_PLAYOFF,
                ronda='Semifinal',
                local=local,
                visitante=visitante,
            ))
    torneo.estado = torneo.ESTADO_PLAYOFFS
    torneo.save(update_fields=['estado'])
    return creados


def avanzar_playoffs(torneo):
    """Crea la Final cuando ambas semifinales tienen ganador.

    Devuelve el partido creado, o None si no corresponde todavía.
    """
    if Partido.objects.filter(torneo=torneo, fase=Partido.FASE_PLAYOFF, ronda='Final').exists():
        return None

    semis = list(Partido.objects.filter(
        torneo=torneo, fase=Partido.FASE_PLAYOFF, ronda='Semifinal',
    ))
    if len(semis) != 2 or any(s.ganador is None for s in semis):
        return None

    return Partido.objects.create(
        torneo=torneo,
        fase=Partido.FASE_PLAYOFF,
        ronda='Final',
        local=semis[0].ganador,
        visitante=semis[1].ganador,
    )


def campeon(torneo):
    """Devuelve el ganador del torneo si la final ya se jugó."""
    final = Partido.objects.filter(
        torneo=torneo, fase=Partido.FASE_PLAYOFF, ronda='Final', jugado=True,
    ).first()
    if final is None:
        return None
    return final.ganador
