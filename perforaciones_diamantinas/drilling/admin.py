from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import *

# ======================================
# FORMULARIOS PERSONALIZADOS PARA USUARIO
# ======================================

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'contrato', 'role')

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = '__all__'

# ======================================
# ADMIN PERSONALIZADO PARA USUARIO
# ======================================

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    list_display = [
        'username', 'email', 'first_name', 'last_name', 
        'role', 'contrato', 'is_active', 'is_system_admin', 'last_activity'
    ]
    list_filter = [
        'role', 'is_system_admin', 'is_active', 'is_staff', 'contrato'
    ]
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['username']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Información del Contrato', {
            'fields': ('contrato', 'role', 'is_system_admin')
        }),
        ('Actividad', {
            'fields': ('last_activity', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 
                      'contrato', 'role', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_activity']

# ======================================
# REGISTRAR MODELOS BÁSICOS
# ======================================

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre']  # Solo campos que existen
    search_fields = ['nombre']
    ordering = ['nombre']

@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ['nombre_contrato', 'cliente', 'duracion_turno', 'estado']  # Solo campos que existen
    list_filter = ['estado', 'cliente']
    search_fields = ['nombre_contrato', 'cliente__nombre']
    ordering = ['nombre_contrato']
    raw_id_fields = ['cliente']

@admin.register(Trabajador)
class TrabajadorAdmin(admin.ModelAdmin):
    list_display = ['apellidos', 'nombres', 'cargo', 'contrato', 'dni', 'is_active']  # Campos básicos que sabemos existen
    list_filter = ['cargo', 'is_active', 'contrato']
    search_fields = ['nombres', 'apellidos', 'dni']
    ordering = ['apellidos', 'nombres']
    raw_id_fields = ['contrato']

@admin.register(Maquina)
class MaquinaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'estado', 'horometro', 'contrato']
    list_filter = ['estado', 'contrato']
    search_fields = ['nombre', 'tipo']
    ordering = ['nombre']
    raw_id_fields = ['contrato']

@admin.register(Sondaje)
class SondajeAdmin(admin.ModelAdmin):
    list_display = ['nombre_sondaje', 'contrato', 'profundidad', 'estado', 'fecha_inicio']
    list_filter = ['estado', 'contrato', 'fecha_inicio']
    search_fields = ['nombre_sondaje', 'contrato__nombre_contrato']
    ordering = ['nombre_sondaje']
    raw_id_fields = ['contrato']

@admin.register(TipoActividad)
class TipoActividadAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion']
    search_fields = ['nombre', 'descripcion']
    ordering = ['nombre']

@admin.register(TipoTurno)
class TipoTurnoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion']
    search_fields = ['nombre', 'descripcion']
    ordering = ['nombre']

@admin.register(TipoComplemento)
class TipoComplementoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'categoria', 'descripcion']
    list_filter = ['categoria']
    search_fields = ['nombre', 'descripcion']
    ordering = ['nombre']

@admin.register(TipoAditivo)
class TipoAditivoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'categoria', 'unidad_medida_default', 'descripcion']
    list_filter = ['categoria']
    search_fields = ['nombre', 'descripcion']
    ordering = ['nombre']
    raw_id_fields = ['unidad_medida_default']

@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'simbolo']
    search_fields = ['nombre', 'simbolo']
    ordering = ['nombre']

# ======================================
# MODELOS DE TURNO (SIMPLIFICADOS)
# ======================================

@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_sondajes_display', 'fecha', 'maquina', 'tipo_turno']
    list_filter = ['fecha', 'tipo_turno', 'sondajes__contrato']
    search_fields = ['sondajes__nombre_sondaje', 'maquina__nombre']
    date_hierarchy = 'fecha'
    ordering = ['-fecha']
    raw_id_fields = ['maquina', 'tipo_turno']

    def get_sondajes_display(self, obj):
        return ', '.join([s.nombre_sondaje for s in obj.sondajes.all()[:3]])
    get_sondajes_display.short_description = 'Sondajes'

# Solo registrar si estos modelos existen
try:
    @admin.register(EstadoTurno)
    class EstadoTurnoAdmin(admin.ModelAdmin):
        list_display = ['nombre', 'descripcion']
        search_fields = ['nombre', 'descripcion']
        ordering = ['nombre']
except:
    pass

try:
    @admin.register(TurnoTrabajador)
    class TurnoTrabajadorAdmin(admin.ModelAdmin):
        list_display = ['turno', 'trabajador', 'funcion']
        list_filter = ['funcion']
        search_fields = ['trabajador__nombres', 'trabajador__apellidos', 'trabajador__dni', 'turno__sondajes__nombre_sondaje']
        raw_id_fields = ['turno', 'trabajador']
except:
    pass

try:
    @admin.register(TurnoComplemento)
    class TurnoComplementoAdmin(admin.ModelAdmin):
        list_display = ['turno', 'tipo_complemento', 'codigo_serie']
        search_fields = ['codigo_serie', 'turno__sondajes__nombre_sondaje']
        raw_id_fields = ['turno', 'tipo_complemento']
except:
    pass

try:
    @admin.register(TurnoAditivo)
    class TurnoAditivoAdmin(admin.ModelAdmin):
        list_display = ['turno', 'tipo_aditivo', 'cantidad_usada']
        search_fields = ['turno__sondajes__nombre_sondaje', 'tipo_aditivo__nombre']
        raw_id_fields = ['turno', 'tipo_aditivo']
except:
    pass

try:
    @admin.register(TurnoActividad)
    class TurnoActividadAdmin(admin.ModelAdmin):
        list_display = ['turno', 'actividad', 'hora_inicio', 'hora_fin']
        search_fields = ['turno__sondajes__nombre_sondaje', 'actividad__nombre']
        raw_id_fields = ['turno', 'actividad']
except:
    pass

try:
    @admin.register(TurnoCorrida)
    class TurnoCorridaAdmin(admin.ModelAdmin):
        list_display = ['turno', 'corrida_numero', 'desde', 'hasta']
        search_fields = ['turno__sondajes__nombre_sondaje', 'corrida_numero']
        raw_id_fields = ['turno']
except:
    pass

try:
    @admin.register(TurnoAvance)
    class TurnoAvanceAdmin(admin.ModelAdmin):
        list_display = ['turno', 'metros_perforados']
        search_fields = ['turno__sondajes__nombre_sondaje']
        raw_id_fields = ['turno']
except:
    pass

try:
    @admin.register(Abastecimiento)
    class AbastecimientoAdmin(admin.ModelAdmin):
        list_display = ['descripcion', 'contrato', 'familia', 'cantidad', 'unidad_medida', 'fecha']
        list_filter = ['familia', 'contrato', 'fecha']
        search_fields = ['descripcion', 'codigo_producto']
        date_hierarchy = 'fecha'
        ordering = ['-fecha']
        raw_id_fields = ['contrato', 'unidad_medida', 'tipo_complemento', 'tipo_aditivo']
except:
    pass

try:
    @admin.register(ConsumoStock)
    class ConsumoStockAdmin(admin.ModelAdmin):
        list_display = ['turno', 'abastecimiento', 'cantidad_consumida']  # Sin fecha_consumo
        search_fields = ['turno__sondajes__nombre_sondaje', 'abastecimiento__descripcion']
        ordering = ['-id']  # Ordenar por ID en lugar de fecha
        raw_id_fields = ['turno', 'abastecimiento']
except:
    pass
