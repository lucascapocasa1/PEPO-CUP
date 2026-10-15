from django import forms

from .models import EventoPartido, Partido


class ResultadoForm(forms.ModelForm):
    class Meta:
        model = Partido
        fields = ['goles_local', 'goles_visitante', 'penales_local', 'penales_visitante', 'jugado']
        widgets = {
            'goles_local': forms.NumberInput(attrs={'class': 'input-marcador', 'inputmode': 'numeric', 'min': 0}),
            'goles_visitante': forms.NumberInput(attrs={'class': 'input-marcador', 'inputmode': 'numeric', 'min': 0}),
            'penales_local': forms.NumberInput(attrs={'class': 'input-penales', 'inputmode': 'numeric', 'min': 0}),
            'penales_visitante': forms.NumberInput(attrs={'class': 'input-penales', 'inputmode': 'numeric', 'min': 0}),
            'jugado': forms.CheckboxInput(attrs={'class': 'check-jugado'}),
        }
        labels = {
            'goles_local': 'Goles',
            'goles_visitante': 'Goles',
            'penales_local': 'Penales',
            'penales_visitante': 'Penales',
            'jugado': 'Marcar como jugado',
        }


class EventoForm(forms.ModelForm):
    class Meta:
        model = EventoPartido
        fields = ['jugador', 'tipo', 'minuto']
        widgets = {
            'jugador': forms.Select(attrs={'class': 'select-jugador'}),
            'tipo': forms.Select(attrs={'class': 'select-tipo'}),
            'minuto': forms.NumberInput(attrs={'class': 'input-minuto', 'inputmode': 'numeric', 'min': 1, 'max': 120}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['jugador'].empty_label = 'Elegí jugador'
        # El label vacío del ChoiceField hay que ponerlo en los choices
        self.fields['tipo'].choices = [('', 'Tipo')] + [
            c for c in self.fields['tipo'].choices if c[0]
        ]


class BaseEventoFormSet(forms.BaseInlineFormSet):
    """Validación suave: filas vacías se ignoran, filas con jugador pero sin tipo dan error."""

    def clean(self):
        super().clean()
        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            jugador = form.cleaned_data.get('jugador')
            tipo = form.cleaned_data.get('tipo')
            if jugador and not tipo:
                raise forms.ValidationError(
                    'Cada gol o asistencia necesita un tipo. Elegí "Gol" o "Asistencia".'
                )


EventoFormSet = forms.inlineformset_factory(
    Partido,
    EventoPartido,
    form=EventoForm,
    formset=BaseEventoFormSet,
    extra=6,
    can_delete=False,
    min_num=0,
    validate_min=False,
)
