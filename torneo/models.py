from pathlib import Path

from django.conf import settings
from django.db import models
from django.urls import reverse


class Torneo(models.Model):
    ESTADO_LIGA = 'liga'
    ESTADO_PLAYOFFS = 'playoffs'
    ESTADO_FINALIZADO = 'finalizado'
    ESTADOS = [
        (ESTADO_LIGA, 'Liga en curso'),
        (ESTADO_PLAYOFFS, 'Playoffs'),
        (ESTADO_FINALIZADO, 'Finalizado'),
    ]

    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_LIGA)
    descripcion = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado']

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse('torneo_detalle', args=[self.slug])


class Participante(models.Model):
    FORMACIONES = [
        '4-4-2', '4-3-1-2', '4-3-3', '4-2-3-1', '4-1-2-1-2',
        '4-2-2-2', '4-5-1', '3-5-2', '5-3-2', '5-4-1', '3-4-3',
    ]

    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='participantes')
    nombre = models.CharField(max_length=60)
    apodo = models.CharField(max_length=40, blank=True)
    club = models.CharField(max_length=60, blank=True, help_text='Nombre de su equipo FUT')
    formacion = models.CharField(max_length=10, choices=[(f, f) for f in FORMACIONES], default='4-3-1-2')
    orden = models.PositiveIntegerField(default=0, help_text='Seed / posición de la liga')
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['orden', 'nombre']
        unique_together = [('torneo', 'nombre')]

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse('participante_detalle', args=[self.torneo.slug, self.pk])

    @property
    def display(self):
        return self.apodo or self.nombre

    def titulares(self):
        return self.jugadores.filter(titular=True).order_by('orden')

    def suplentes(self):
        return self.jugadores.filter(titular=False).order_by('orden')


class JugadorFUT(models.Model):
    POSICIONES = [('POR', 'POR'), ('DEF', 'DEF'), ('MED', 'MED'), ('DEL', 'DEL')]

    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name='jugadores')
    nombre = models.CharField(max_length=60)
    posicion = models.CharField(max_length=3, choices=POSICIONES, default='MED')
    rating = models.PositiveSmallIntegerField(default=84)
    carta = models.CharField(
        max_length=120, blank=True,
        help_text='Archivo de la carta en static/cartas/ (ej: mbappe.png). Se puede dejar vacío.',
    )
    titular = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0, help_text='Orden dentro de la alineación')

    class Meta:
        ordering = ['orden', 'nombre']
        unique_together = [('participante', 'nombre')]

    def __str__(self):
        return f'{self.nombre} ({self.participante.display})'

    @property
    def carta_url(self):
        """URL de la carta FUT. None si no hay imagen o el archivo no existe todavía.

        Busca primero el nombre exacto y después con otras extensiones
        (jpg, webp...), así da igual cómo se haya guardado la imagen.
        """
        if not self.carta:
            return None
        base = Path(settings.BASE_DIR) / 'static' / 'cartas'
        nombre = Path(self.carta)
        if (base / nombre.name).exists():
            return f'/static/cartas/{nombre.name}'
        for extension in ('.png', '.jpg', '.jpeg', '.webp'):
            if (base / f'{nombre.stem}{extension}').exists():
                return f'/static/cartas/{nombre.stem}{extension}'
        return None


class Partido(models.Model):
    FASE_LIGA = 'liga'
    FASE_PLAYOFF = 'playoff'
    FASES = [(FASE_LIGA, 'Liga'), (FASE_PLAYOFF, 'Playoff')]

    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='partidos')
    fase = models.CharField(max_length=10, choices=FASES, default=FASE_LIGA)
    ronda = models.CharField(max_length=40, help_text='Ej: "Fecha 1", "Semifinal", "Final"')
    local = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name='como_local')
    visitante = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name='como_visitante')
    goles_local = models.PositiveSmallIntegerField(null=True, blank=True)
    goles_visitante = models.PositiveSmallIntegerField(null=True, blank=True)
    penales_local = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text='Solo eliminatorias: penales si termina empatado',
    )
    penales_visitante = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text='Solo eliminatorias: penales si termina empatado',
    )
    jugado = models.BooleanField(default=False)
    fecha = models.DateTimeField(null=True, blank=True)
    figura = models.ForeignKey(
        JugadorFUT, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='figuras', help_text='Jugador FUT figura del partido',
    )

    class Meta:
        ordering = ['fecha', 'ronda', 'pk']

    def __str__(self):
        return f'{self.local.display} {self.goles_local or "-"} - {self.goles_visitante or "-"} {self.visitante.display}'

    def get_absolute_url(self):
        return reverse('partido_detalle', args=[self.pk])

    @property
    def marcador(self):
        if self.goles_local is None or self.goles_visitante is None:
            return 'vs'
        return f'{self.goles_local} - {self.goles_visitante}'

    @property
    def ganador(self):
        """Devuelve el Participante ganador o None si es empate / no jugado."""
        if not self.jugado or self.goles_local is None or self.goles_visitante is None:
            return None
        if self.goles_local > self.goles_visitante:
            return self.local
        if self.goles_visitante > self.goles_local:
            return self.visitante
        # Empate: en eliminatorias se define por penales
        if (
            self.fase == self.FASE_PLAYOFF
            and self.penales_local is not None
            and self.penales_visitante is not None
        ):
            if self.penales_local > self.penales_visitante:
                return self.local
            if self.penales_visitante > self.penales_local:
                return self.visitante
        return None

    @property
    def empatado(self):
        return (
            self.jugado
            and self.goles_local is not None
            and self.goles_local == self.goles_visitante
        )

    def goles(self):
        return self.eventos.filter(tipo=EventoPartido.TIPO_GOL)

    def asistencias(self):
        return self.eventos.filter(tipo=EventoPartido.TIPO_ASISTENCIA)


class EventoPartido(models.Model):
    TIPO_GOL = 'gol'
    TIPO_AUTOGOL = 'autogol'
    TIPO_ASISTENCIA = 'asistencia'
    TIPOS = [
        (TIPO_GOL, 'Gol'),
        (TIPO_AUTOGOL, 'Autogol'),
        (TIPO_ASISTENCIA, 'Asistencia'),
    ]

    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='eventos')
    jugador = models.ForeignKey(JugadorFUT, on_delete=models.CASCADE, related_name='eventos')
    tipo = models.CharField(max_length=10, choices=TIPOS)
    minuto = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Minuto (opcional)')

    class Meta:
        ordering = ['minuto', 'pk']

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.jugador.nombre}'
