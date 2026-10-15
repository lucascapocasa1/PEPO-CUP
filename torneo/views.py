from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import services
from .forms import EventoFormSet, ResultadoForm
from .models import Partido, Participante, Torneo


def get_torneo(slug=None):
    """Devuelve el torneo pedido por slug, o el activo más reciente."""
    if slug:
        return get_object_or_404(Torneo, slug=slug)
    torneo = (
        Torneo.objects.exclude(estado=Torneo.ESTADO_FINALIZADO).order_by('-creado').first()
        or Torneo.objects.order_by('-creado').first()
    )
    return torneo


def contexto_torneo(torneo):
    """Contexto común para las páginas del torneo."""
    tabla = services.tabla_posiciones(torneo)
    partidos = torneo.partidos.select_related('local', 'visitante', 'figura')
    jugados = [p for p in partidos if p.jugado]
    pendientes = [p for p in partidos if not p.jugado]
    ultimos = sorted(jugados, key=lambda p: (p.fecha is None, p.fecha or ''), reverse=True)[:5]
    proximos = [p for p in pendientes if p.fecha] + [p for p in pendientes if not p.fecha]
    proximos = proximos[:5]

    return {
        'torneo': torneo,
        'tabla': tabla,
        'ultimos_resultados': ultimos,
        'proximos_partidos': proximos,
        'goleadores': services.tabla_goleadores(torneo, limite=5),
        'campeon': services.campeon(torneo),
        'participantes': torneo.participantes.filter(activo=True),
    }


# ---------------------------------------------------------------------------
# Páginas públicas
# ---------------------------------------------------------------------------

def home(request):
    torneo = get_torneo()
    if torneo is None:
        return render(request, 'torneo/sin_torneos.html')
    return render(request, 'torneo/home.html', contexto_torneo(torneo))


def torneo_lista(request):
    torneos = Torneo.objects.all()
    return render(request, 'torneo/torneo_lista.html', {'torneos': torneos})


def torneo_detalle(request, slug):
    torneo = get_torneo(slug)
    return render(request, 'torneo/home.html', contexto_torneo(torneo))


def participantes(request, slug):
    torneo = get_torneo(slug)
    participantes_qs = torneo.participantes.filter(activo=True)
    return render(request, 'torneo/participantes.html', {
        'torneo': torneo,
        'participantes': participantes_qs,
    })


def participante_detalle(request, slug, pk):
    torneo = get_torneo(slug)
    participante = get_object_or_404(Participante, torneo=torneo, pk=pk)

    partidos = list(
        torneo.partidos.filter(Q(local=participante) | Q(visitante=participante))
        .select_related('local', 'visitante', 'figura')
    )
    jugados = [p for p in partidos if p.jugado]
    proximos = [p for p in partidos if not p.jugado]

    return render(request, 'torneo/participante_detalle.html', {
        'torneo': torneo,
        'p': participante,
        'titulares': participante.titulares(),
        'suplentes': participante.suplentes(),
        'proximos': proximos,
        'resultados': jugados,
        'stats': services.stats_participante(participante),
        'mis_goleadores': services.tabla_goleadores(torneo),
    })


def partidos(request, slug):
    torneo = get_torneo(slug)
    partidos_qs = torneo.partidos.select_related('local', 'visitante', 'figura').order_by('fase', 'ronda', 'fecha', 'pk')

    fechas = {}
    for partido in partidos_qs:
        if partido.fase == Partido.FASE_PLAYOFF:
            clave = f'Playoffs — {partido.ronda}'
        else:
            clave = partido.ronda
        fechas.setdefault(clave, []).append(partido)

    return render(request, 'torneo/partidos.html', {'torneo': torneo, 'fechas': fechas})


def partido_detalle(request, pk):
    partido = get_object_or_404(
        Partido.objects.select_related('local', 'visitante', 'figura', 'torneo'), pk=pk,
    )
    goles = partido.goles().select_related('jugador', 'jugador__participante')
    asistencias = partido.asistencias().select_related('jugador', 'jugador__participante')

    return render(request, 'torneo/partido_detalle.html', {
        'torneo': partido.torneo,
        'partido': partido,
        'goles': goles,
        'asistencias': asistencias,
        'local_titulares': partido.local.titulares(),
        'visitante_titulares': partido.visitante.titulares(),
    })


def goleadores(request, slug):
    torneo = get_torneo(slug)
    return render(request, 'torneo/goleadores.html', {
        'torneo': torneo,
        'goleadores': services.tabla_goleadores(torneo),
    })


# ---------------------------------------------------------------------------
# Carga de resultados (organizador, desde el celular)
# ---------------------------------------------------------------------------

@login_required
def cargar(request):
    """Lista de partidos pendientes para cargar rápido."""
    torneo = get_torneo()
    partidos = []
    if torneo:
        partidos = torneo.partidos.select_related('local', 'visitante').order_by('fase', 'ronda', 'pk')
    return render(request, 'torneo/cargar.html', {
        'torneo': torneo,
        'partidos': partidos,
        'pendientes': [p for p in partidos if not p.jugado],
        'jugados': [p for p in partidos if p.jugado],
    })


@login_required
def cargar_partido(request, pk):
    partido = get_object_or_404(Partido.objects.select_related('local', 'visitante', 'torneo'), pk=pk)
    torneo = partido.torneo

    # Jugadores FUT disponibles: los de los dos equipos del partido
    jugadores = partido.local.jugadores.all() | partido.visitante.jugadores.all()
    jugadores = jugadores.order_by('participante__nombre', 'orden')

    if request.method == 'POST':
        resultado_form = ResultadoForm(request.POST, instance=partido)
        formset = EventoFormSet(request.POST, instance=partido)
        if resultado_form.is_valid() and formset.is_valid():
            with transaction.atomic():
                partido = resultado_form.save(commit=False)
                figura_id = request.POST.get('figura')
                partido.figura_id = int(figura_id) if figura_id else None
                if not partido.jugado:
                    partido.goles_local = None
                    partido.goles_visitante = None
                partido.save()
                formset.save()

                # Si es una eliminatoria, intentamos avanzar a la final
                if partido.fase == Partido.FASE_PLAYOFF:
                    services.avanzar_playoffs(torneo)

            return redirect('cargar')
    else:
        resultado_form = ResultadoForm(instance=partido)
        formset = EventoFormSet(instance=partido)

    return render(request, 'torneo/cargar_partido.html', {
        'partido': partido,
        'torneo': torneo,
        'resultado_form': resultado_form,
        'formset': formset,
        'jugadores': jugadores,
        'figuras_posibles': jugadores,
    })
