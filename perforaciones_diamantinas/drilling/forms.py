from django import forms
from django.core.exceptions import ValidationError
from .models import *

class TrabajadorForm(forms.ModelForm):
    class Meta:
        model = Trabajador
        fields = ['nombres', 'apellidos', 'cargo', 'dni', 'telefono', 'email', 'fecha_ingreso', 'is_active']
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombres'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellidos'}),
            'cargo': forms.Select(attrs={'class': 'form-select'}),
            'dni': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'DNI o documento de identidad'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 9 1234 5678'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'fecha_ingreso': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if dni:
            dni = dni.strip()
            # Validación básica: longitud razonable
            if len(dni) < 6 or len(dni) > 20:
                raise ValidationError("Formato de DNI inválido")
        return dni

class MaquinaForm(forms.ModelForm):
    class Meta:
        model = Maquina
        fields = ['nombre', 'tipo', 'estado', 'horometro']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la máquina'}),
            'tipo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tipo/Modelo de máquina'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'horometro': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

class SondajeForm(forms.ModelForm):
    class Meta:
        model = Sondaje
        fields = ['nombre_sondaje', 'fecha_inicio', 'fecha_fin', 'profundidad', 'inclinacion', 'cota_collar', 'estado']
        widgets = {
            'nombre_sondaje': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del sondaje'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'profundidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'inclinacion': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '-90', 'max': '90'}),
            'cota_collar': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')

        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            raise ValidationError("La fecha de fin debe ser posterior a la fecha de inicio")

        return cleaned_data

class TipoActividadForm(forms.ModelForm):
    class Meta:
        model = TipoActividad
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la actividad'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción opcional'}),
        }

class TipoTurnoForm(forms.ModelForm):
    class Meta:
        model = TipoTurno
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del tipo de turno'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción opcional'}),
        }

class TipoComplementoForm(forms.ModelForm):
    class Meta:
        model = TipoComplemento
        fields = ['nombre', 'categoria', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del complemento'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción opcional'}),
        }

class TipoAditivoForm(forms.ModelForm):
    class Meta:
        model = TipoAditivo
        fields = ['nombre', 'categoria', 'unidad_medida_default', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del aditivo'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'unidad_medida_default': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción opcional'}),
        }

class UnidadMedidaForm(forms.ModelForm):
    class Meta:
        model = UnidadMedida
        fields = ['nombre', 'simbolo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la unidad'}),
            'simbolo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Símbolo (ej: kg, m, L)'}),
        }

class AbastecimientoForm(forms.ModelForm):
    class Meta:
        model = Abastecimiento
        fields = [
            'mes', 'fecha', 'contrato', 'codigo_producto', 'descripcion', 'familia', 'serie',
            'unidad_medida', 'cantidad', 'precio_unitario', 'tipo_complemento', 'tipo_aditivo',
            'numero_guia', 'observaciones'
        ]
        widgets = {
            'mes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ENERO, FEBRERO, etc.'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'contrato': forms.Select(attrs={'class': 'form-select'}),
            'codigo_producto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código del producto'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción del producto'}),
            'familia': forms.Select(attrs={'class': 'form-select'}),
            'serie': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de serie'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'tipo_complemento': forms.Select(attrs={'class': 'form-select'}),
            'tipo_aditivo': forms.Select(attrs={'class': 'form-select'}),
            'numero_guia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de guía'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observaciones adicionales'}),
        }

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad and cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor a 0")
        return cantidad

    def clean_precio_unitario(self):
        precio = self.cleaned_data.get('precio_unitario')
        if precio and precio <= 0:
            raise ValidationError("El precio unitario debe ser mayor a 0")
        return precio

class ConsumoStockForm(forms.ModelForm):
    class Meta:
        model = ConsumoStock
        fields = [
            'turno', 'abastecimiento', 'cantidad_consumida', 'serie_utilizada',
            'metros_inicio', 'metros_fin', 'estado_final', 'observaciones'
        ]
        widgets = {
            'turno': forms.Select(attrs={'class': 'form-select'}),
            'abastecimiento': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_consumida': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'serie_utilizada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Serie del producto utilizado'}),
            'metros_inicio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'metros_fin': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'estado_final': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observaciones del consumo'}),
        }

    def clean_cantidad_consumida(self):
        cantidad = self.cleaned_data.get('cantidad_consumida')
        if cantidad and cantidad <= 0:
            raise ValidationError("La cantidad consumida debe ser mayor a 0")
        return cantidad

    def clean(self):
        cleaned_data = super().clean()
        metros_inicio = cleaned_data.get('metros_inicio')
        metros_fin = cleaned_data.get('metros_fin')

        if metros_inicio and metros_fin and metros_fin < metros_inicio:
            raise ValidationError("Los metros fin deben ser mayores a los metros inicio")

        return cleaned_data


class TurnoForm(forms.ModelForm):
    class Meta:
        model = Turno
        # sondajes ahora es un campo M2M; usar un select múltiple en el formulario
        fields = ['sondajes', 'maquina', 'tipo_turno', 'fecha', 'estado']
        widgets = {
            'sondajes': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
            'maquina': forms.Select(attrs={'class': 'form-select'}),
            'tipo_turno': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }


class TurnoMaquinaForm(forms.ModelForm):
    class Meta:
        model = TurnoMaquina
        fields = ['hora_inicio', 'hora_fin', 'estado_bomba', 'estado_unidad', 'estado_rotacion']
        widgets = {
            'hora_inicio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'estado_bomba': forms.Select(attrs={'class': 'form-select'}),
            'estado_unidad': forms.Select(attrs={'class': 'form-select'}),
            'estado_rotacion': forms.Select(attrs={'class': 'form-select'}),
        }


class TurnoAvanceForm(forms.ModelForm):
    class Meta:
        model = TurnoAvance
        fields = ['metros_perforados']
        widgets = {
            'metros_perforados': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }