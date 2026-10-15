from django.contrib import admin, messages
from django.utils.html import format_html

from . import services
from .models import EventoPartido, JugadorFUT, Partido, Participante, Torneo


class JugadorFUTInline(admin.TabularInline):
    model = JugadorFUT
    extra = 0
    fields = ('orden', 'nombre', 'posicion', 'rating', 'titular', 'carta')
    ordering = ('orden',)


@admin.register(Torneo)
class TorneoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'estado', 'creado')
    prepopulated_fields = {'slug': ('nombre',)}
    actions = ['accion_generar_fixture', 'accion_generar_playoffs', 'accion_avanzar_playoffs']

    @admin.action(description='⚙️ Generar fixture de liga (ida, todos contra todos)')
    def accion_generar_fixture(self, request, queryset):
        for torneo in queryset:
            cantidad = services.generar_fixture_liga(torneo)
            self.message_user(
                request,
                f'{torneo.nombre}: fixture de liga generado con {cantidad} partidos.',
                messages.SUCCESS,
            )

    @admin.action(description='🏆 Generar playoffs (semifinales según la tabla)')
    def accion_generar_playoffs(self, request, queryset):
        for torneo in queryset:
            creados = services.generar_playoffs(torneo)
            if creados is None:
                self.message_user(
                    request,
                    f'{torneo.nombre}: faltan participantes para armar los playoffs.',
                    messages.WARNING,
                )
            else:
                self.message_user(
                    request,
                    f'{torneo.nombre}: semifinales creadas.',
                    messages.SUCCESS,
                )

    @admin.action(description='➡️ Crear la Final (si ya se jugaron las semifinales)')
    def accion_avanzar_playoffs(self, request, queryset):
        for torneo in queryset:
            final = services.avanzar_playoffs(torneo)
            if final is None:
                self.message_user(
                    request,
                    f'{torneo.nombre}: todavía no corresponde crear la final.',
                    messages.WARNING,
                )
            else:
                self.message_user(request, f'{torneo.nombre}: final creada.', messages.SUCCESS)


@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'torneo', 'club', 'formacion', 'activo')
    list_filter = ('torneo',)
    search_fields = ('nombre', 'apodo', 'club')
    inlines = [JugadorFUTInline]


@admin.register(JugadorFUT)
class JugadorFUTAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'participante', 'posicion', 'rating', 'titular', 'ver_carta')
    list_filter = ('participante__torneo', 'posicion', 'titular')
    search_fields = ('nombre', 'participante__nombre')

    @admin.display(description='Carta')
    def ver_carta(self, obj):
        if obj.carta_url:
            return format_html('<img src="{}" style="height:60px">', obj.carta_url)
        return '—'


@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    list_display = ('ronda', 'marcador_tabla', 'local', 'visitante', 'jugado', 'figura')
    list_filter = ('torneo', 'fase', 'ronda', 'jugado')
    list_editable = ('jugado',)
    autocomplete_fields = ('figura',)
    search_fields = ('local__nombre', 'visitante__nombre', 'ronda')

    @admin.display(description='Resultado', ordering='goles_local')
    def marcador_tabla(self, obj):
        return str(obj)


@admin.register(EventoPartido)
class EventoPartidoAdmin(admin.ModelAdmin):
    list_display = ('partido', 'tipo', 'jugador', 'minuto')
    list_filter = ('tipo', 'partido__torneo')
    autocomplete_fields = ('jugador', 'partido')
