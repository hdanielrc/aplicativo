from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal

class Cliente(models.Model):
    nombre = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'clientes'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.nombre

class Contrato(models.Model):
    ESTADO_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('SUSPENDIDO', 'Suspendido'),
        ('FINALIZADO', 'Finalizado'),
    ]
    
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='contratos')
    nombre_contrato = models.CharField(max_length=200)
    duracion_turno = models.PositiveIntegerField(default=8)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='ACTIVO')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Actividades disponibles/permitidas para este contrato (maestro compartido)
    # Usamos un modelo `through` que mapea a la tabla legacy `contratos_actividades`
    # existente en la base de datos. El modelo `ContratoActividad` se declara
    # más abajo y tiene `Meta.managed = False` para no intentar recrear la
    # tabla en migraciones (la tabla ya existe en la BD según lo indicado).
    actividades = models.ManyToManyField('TipoActividad', blank=True, related_name='contratos', through='ContratoActividad')

    class Meta:
        db_table = 'contratos'
        verbose_name = 'Contrato'
        verbose_name_plural = 'Contratos'

    def __str__(self):
        return f"{self.cliente.nombre} - {self.nombre_contrato}"

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class CustomUser(AbstractUser):
    """Usuario personalizado con roles y contrato asignado"""
    
    # Definición de roles del sistema
    USER_ROLES = [
        ('ADMIN_SISTEMA', 'Administrador del Sistema'),
        ('MANAGER_CONTRATO', 'Manager de Contrato'),
        ('SUPERVISOR', 'Supervisor de Operaciones'), 
        ('OPERADOR', 'Operador Regular'),
    ]
    
    # Campos adicionales
    contrato = models.ForeignKey(
        'Contrato', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name='Contrato asignado',
        help_text='Contrato al que pertenece este usuario'
    )
    
    role = models.CharField(
        max_length=20, 
        choices=USER_ROLES, 
        default='OPERADOR',
        verbose_name='Rol del usuario',
        help_text='Define los permisos y accesos del usuario'
    )
    
    is_system_admin = models.BooleanField(
        default=False,
        verbose_name='Es administrador del sistema',
        help_text='Marca si este usuario es administrador de todo el sistema'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última actualización'
    )
    
    last_activity = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='Última actividad',
        help_text='Última vez que el usuario accedió al sistema'
    )
    
    # Métodos de permisos por rol
    def can_manage_all_contracts(self):
        """Solo admin del sistema puede gestionar todos los contratos"""
        return self.role == 'ADMIN_SISTEMA' and self.is_system_admin
    
    def can_manage_contract_users(self):
        """Manager y Admin pueden gestionar usuarios del contrato"""
        return self.role in ['ADMIN_SISTEMA', 'MANAGER_CONTRATO']
    
    def can_supervise_operations(self):
        """Supervisor y superiores pueden supervisar operaciones"""  
        return self.role in ['ADMIN_SISTEMA', 'MANAGER_CONTRATO', 'SUPERVISOR']
    
    def can_create_basic_data(self):
        """Crear datos básicos (trabajadores, máquinas, sondajes)"""
        return self.role in ['ADMIN_SISTEMA', 'MANAGER_CONTRATO', 'SUPERVISOR']
    
    def can_manage_inventory(self):
        """Gestionar inventario y abastecimiento"""
        return self.role in ['ADMIN_SISTEMA', 'MANAGER_CONTRATO']
    
    def can_import_data(self):
        """Importar datos desde Excel"""
        return self.role in ['ADMIN_SISTEMA', 'MANAGER_CONTRATO']
    
    def can_view_reports(self):
        """Ver reportes del sistema"""
        return self.role in ['ADMIN_SISTEMA', 'MANAGER_CONTRATO', 'SUPERVISOR']
    
    def can_manage_system_config(self):
        """Gestionar configuración del sistema (tipos, unidades, etc.)"""
        return self.role in ['ADMIN_SISTEMA', 'MANAGER_CONTRATO']
    
    def get_accessible_contracts(self):
        """Obtener contratos accesibles según el rol"""
        if self.role == 'ADMIN_SISTEMA':
            from .models import Contrato  # Import here to avoid circular imports
            return Contrato.objects.all()
        else:
            from .models import Contrato
            return Contrato.objects.filter(id=self.contrato_id) if self.contrato else Contrato.objects.none()
    
    def get_role_display(self):
        """Obtener el nombre legible del rol"""
        return dict(self.USER_ROLES).get(self.role, self.role)
    
    def get_role_badge_class(self):
        """Obtener la clase CSS para el badge del rol"""
        role_classes = {
            'ADMIN_SISTEMA': 'bg-danger',
            'MANAGER_CONTRATO': 'bg-warning text-dark',
            'SUPERVISOR': 'bg-info',
            'OPERADOR': 'bg-secondary',
        }
        return role_classes.get(self.role, 'bg-secondary')
    
    def get_permissions_summary(self):
        """Obtener resumen de permisos para mostrar en admin o perfiles"""
        permissions = []
        
        if self.can_manage_all_contracts():
            permissions.append("Gestionar todos los contratos")
        if self.can_manage_contract_users():
            permissions.append("Gestionar usuarios del contrato")
        if self.can_supervise_operations():
            permissions.append("Supervisar operaciones")
        if self.can_create_basic_data():
            permissions.append("Crear datos básicos")
        if self.can_manage_inventory():
            permissions.append("Gestionar inventario")
        if self.can_import_data():
            permissions.append("Importar datos")
        if self.can_view_reports():
            permissions.append("Ver reportes")
        if self.can_manage_system_config():
            permissions.append("Configuración del sistema")
            
        return permissions
    
    def is_active_recently(self, days=30):
        """Verificar si el usuario ha estado activo recientemente"""
        if not self.last_activity:
            return False
        
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.last_activity >= cutoff_date
    
    def update_last_activity(self):
        """Actualizar la última actividad del usuario"""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    def get_contract_display(self):
        """Obtener información del contrato para mostrar"""
        if self.contrato:
            return f"{self.contrato.nombre_contrato} ({self.contrato.cliente.nombre})"
        return "Sin contrato asignado"
    
    def has_contract_permission(self, contract):
        """Verificar si el usuario tiene permisos sobre un contrato específico"""
        if self.can_manage_all_contracts():
            return True
        return self.contrato == contract
    
    def clean(self):
        """Validaciones personalizadas del modelo"""
        from django.core.exceptions import ValidationError
        
        # Admin del sistema debe tener is_system_admin=True
        if self.role == 'ADMIN_SISTEMA' and not self.is_system_admin:
            raise ValidationError({
                'is_system_admin': 'Los administradores del sistema deben tener marcado "Es administrador del sistema"'
            })
        
        # Manager debe tener un contrato asignado
        if self.role == 'MANAGER_CONTRATO' and not self.contrato:
            raise ValidationError({
                'contrato': 'Los managers de contrato deben tener un contrato asignado'
            })
        
        # Usuarios que no son admin del sistema no pueden gestionar todos los contratos
        if self.is_system_admin and self.role != 'ADMIN_SISTEMA':
            raise ValidationError({
                'is_system_admin': 'Solo los usuarios con rol "Administrador del Sistema" pueden ser administradores del sistema'
            })
    
    def save(self, *args, **kwargs):
        """Override save para aplicar validaciones"""
        self.full_clean()
        
        # Asignar is_staff automáticamente para managers
        if self.role == 'MANAGER_CONTRATO':
            self.is_staff = True
        elif self.role == 'ADMIN_SISTEMA':
            self.is_staff = True
            self.is_superuser = True
        else:
            # Operadores y supervisores no tienen acceso al admin por defecto
            if not self.can_manage_all_contracts():
                self.is_staff = False
                self.is_superuser = False
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        """Representación en string del usuario"""
        role_display = self.get_role_display()
        if self.contrato:
            return f"{self.username} ({role_display}) - {self.contrato.nombre_contrato}"
        return f"{self.username} ({role_display})"
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['username']
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['contrato']),
            models.Index(fields=['is_system_admin']),
            models.Index(fields=['last_activity']),
        ]

class TipoTurno(models.Model):
    nombre = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True)

    class Meta:
        db_table = 'tipo_turnos'

    def __str__(self):
        return self.nombre

class EstadoTurno(models.Model):
    nombre = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True)

    class Meta:
        db_table = 'estados_turno'

    def __str__(self):
        return self.nombre

class TipoActividad(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    descripcion_corta = models.CharField(max_length=200, blank=True)
    TIPO_CHOICES = [
        ('STAND_BY_CLIENTE', 'Stand By Cliente'),
        ('STAND_BY_ROCKDRILL', 'Stand By Rock Drill'),
        ('INOPERATIVO', 'Inoperativo'),
        ('OPERATIVO', 'Operativo'),
        ('OTROS', 'Otros'),
    ]
    tipo_actividad = models.CharField(max_length=32, choices=TIPO_CHOICES, default='OTROS')

    class Meta:
        db_table = 'tipos_actividad'

    def __str__(self):
        return self.nombre


class ContratoActividad(models.Model):
    """Modelo que mapea la tabla legacy `contratos_actividades`.

    Columnas detectadas: id, contrato_id, tipoactividad_id, tipos_actividad, contrato
    Mapear los campos FK a los modelos actuales y dejar los campos legacy (texto)
    accesibles. `managed = False` para no crear/alterar la tabla desde Django.
    """
    contrato = models.ForeignKey('Contrato', on_delete=models.CASCADE, db_column='contrato_id', related_name='+')
    tipoactividad = models.ForeignKey('TipoActividad', on_delete=models.CASCADE, db_column='tipoactividad_id', related_name='+')
    # columnas legacy/denormalizadas que existían en la tabla
    tipos_actividad = models.CharField(max_length=255, blank=True, null=True)
    contrato_text = models.CharField(max_length=255, blank=True, null=True, db_column='contrato')

    class Meta:
        db_table = 'contratos_actividades'
        managed = False
        verbose_name = 'Contrato Actividad'
        verbose_name_plural = 'Contratos Actividades'
        unique_together = [('contrato', 'tipoactividad')]

    def __str__(self):
        try:
            return f"{self.contrato} - {self.tipoactividad}"
        except Exception:
            return f"ContratoActividad {self.pk}"

class UnidadMedida(models.Model):
    nombre = models.CharField(max_length=50)
    simbolo = models.CharField(max_length=10)

    class Meta:
        db_table = 'unidades_medida'

    def __str__(self):
        return f"{self.nombre} ({self.simbolo})"

class TipoComplemento(models.Model):
    CATEGORIA_CHOICES = [
        ('BROCA', 'Broca'),
        ('REAMING_SHELL', 'Reaming Shell'),
        ('ZAPATA', 'Zapata'),
        ('CORE_LIFTER', 'Core Lifter'),
    ]
    
    nombre = models.CharField(max_length=100)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    descripcion = models.TextField(blank=True)

    class Meta:
        db_table = 'tipos_complemento'

    def __str__(self):
        return self.nombre

class TipoAditivo(models.Model):
    CATEGORIA_CHOICES = [
        ('BENTONITA', 'Bentonita'),
        ('POLIMEROS', 'Polímeros'),
        ('CMC', 'CMC'),
        ('SODA_ASH', 'Soda Ash'),
        ('DISPERSANTE', 'Dispersante'),
        ('LUBRICANTE', 'Lubricante'),
        ('ESPUMANTE', 'Espumante'),
    ]
    
    nombre = models.CharField(max_length=100)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    unidad_medida_default = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT)
    descripcion = models.TextField(blank=True)

    class Meta:
        db_table = 'tipos_aditivo'

    def __str__(self):
        return self.nombre

class Sondaje(models.Model):
    ESTADO_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('PAUSADO', 'Pausado'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    contrato = models.ForeignKey(Contrato, on_delete=models.PROTECT, related_name='sondajes')
    nombre_sondaje = models.CharField(max_length=100)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    profundidad = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('3000.00'))])
    inclinacion = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('-90.00')), MaxValueValidator(Decimal('90.00'))])
    cota_collar = models.DecimalField(max_digits=8, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='ACTIVO')

    class Meta:
        db_table = 'sondajes'
        verbose_name = 'Sondaje'
        verbose_name_plural = 'Sondajes'

    def clean(self):
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError('La fecha de fin debe ser posterior a la fecha de inicio')

    def __str__(self):
        return f"{self.nombre_sondaje} - {self.contrato.nombre_contrato}"

class Maquina(models.Model):
    ESTADO_CHOICES = [
        ('OPERATIVO', 'Operativo'),
        ('MANTENIMIENTO', 'En Mantenimiento'),
        ('FUERA_SERVICIO', 'Fuera de Servicio'),
    ]
    
    contrato = models.ForeignKey(Contrato, on_delete=models.PROTECT, related_name='maquinas')
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=100)
    # Horómetro acumulado en horas (decimal con 2 decimales)
    horometro = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='OPERATIVO')

    class Meta:
        db_table = 'maquinas'

    def __str__(self):
        return f"{self.nombre} - {self.contrato.nombre_contrato}"

class Trabajador(models.Model):
    CARGO_CHOICES = [
        ('RESIDENTE', 'Residente'),
        ('ASISTENTE RESIDENTE', 'Asistente Residente'),
        ('INGENIERO(A) SEGURIDAD', 'Ingeniero Seguridad'),
        ('SUPERVISOR(A) SEGURIDAD', 'Supervisor(a) Seguridad'),
        ('ADMINISTRADOR(A)', 'Administrador(a)'),
        ('TÉCNICO(A) MECÁCNICO', 'Técnico Mecánico'),
        ('PERFORISTA DDH', 'Perforista DDH'),
        ('AYUDANTE', 'Ayudante DDH'),

    ]
    
    contrato = models.ForeignKey(Contrato, on_delete=models.PROTECT, related_name='trabajadores')
    nombres = models.CharField(max_length=200)
    apellidos = models.CharField(max_length=200, blank=True)
    cargo = models.CharField(max_length=30, choices=CARGO_CHOICES)
    dni = models.CharField(max_length=20, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    fecha_ingreso = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trabajadores'
    unique_together = ['contrato', 'dni']

    def __str__(self):
        return f"{self.nombres} {self.apellidos or ''} - {self.get_cargo_display()}"

class Turno(models.Model):
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('COMPLETADO', 'Completado'),
        ('APROBADO', 'Aprobado'),
    ]
    
    # Un turno puede ahora estar asociado a uno o varios sondajes.
    # Usamos un modelo intermedio `TurnoSondaje` (through) para permitir
    # extender la relación en el futuro con datos por sondaje si es necesario.
    sondajes = models.ManyToManyField(Sondaje, related_name='turnos', through='TurnoSondaje', blank=True)
    maquina = models.ForeignKey(Maquina, on_delete=models.PROTECT, related_name='turnos')
    tipo_turno = models.ForeignKey(TipoTurno, on_delete=models.PROTECT)
    fecha = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='BORRADOR')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'turnos'
    # Ajuste: la unicidad ahora se mantiene por máquina/fecha/tipo_turno.
    # La asociación sondaje->turno es M2M, por lo que no formará parte
    # de esta constraint. Esto evita duplicados de turno para la misma
    # máquina/fecha/tipo.
    unique_together = ['maquina', 'fecha', 'tipo_turno']

    def __str__(self):
        try:
            # Mostrar uno o varios sondajes si existen
            if self.pk:
                sondajes = list(self.sondajes.all()[:3])
                if len(sondajes) == 1:
                    return f"Turno {self.id} - {sondajes[0].nombre_sondaje} - {self.fecha}"
                elif len(sondajes) > 1:
                    names = ', '.join([s.nombre_sondaje for s in sondajes])
                    return f"Turno {self.id} - {names} - {self.fecha}"
        except Exception:
            pass
        return f"Turno {self.id} - {self.fecha}"

class TurnoTrabajador(models.Model):
    FUNCION_CHOICES = [
        ('PERFORISTA', 'Perforista'),
        ('AYUDANTE', 'Ayudante'),
    ]
    
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name='trabajadores_turno')
    trabajador = models.ForeignKey(Trabajador, on_delete=models.PROTECT)
    funcion = models.CharField(max_length=30, choices=FUNCION_CHOICES)
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = 'turno_trabajador'
        unique_together = ['turno', 'trabajador']
    
class TurnoSondaje(models.Model):
    """Modelo intermedio que asocia un Turno con un Sondaje.

    Dejarlo simple por ahora (turno, sondaje, created_at). En el futuro se
    pueden añadir métricas por sondaje (metros_perforados, observaciones, etc.)
    sin romper la relación M2M.
    """
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name='turno_sondajes')
    sondaje = models.ForeignKey(Sondaje, on_delete=models.PROTECT, related_name='sondaje_turnos')
    metros_turno = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'turno_sondaje'
        unique_together = ['turno', 'sondaje']

    def __str__(self):
        return f"Turno {self.turno_id} - Sondaje {self.sondaje_id}"


class TurnoAvance(models.Model):
    turno = models.OneToOneField(Turno, on_delete=models.CASCADE, related_name='avance')
    metros_perforados = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'turno_avance'

class TurnoMaquina(models.Model):
    ESTADO_CHOICES = [
        ('OPERATIVO', 'Operativo'),
        ('DEFICIENTE', 'Deficiente'),
        ('INOPERATIVO', 'Inoperativo'),
    ]
    
    turno = models.OneToOneField(Turno, on_delete=models.CASCADE, related_name='maquina_estado')
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    horas_trabajadas_calc = models.DecimalField(max_digits=4, decimal_places=2, editable=False)
    estado_bomba = models.CharField(max_length=20, choices=ESTADO_CHOICES)
    estado_unidad = models.CharField(max_length=20, choices=ESTADO_CHOICES)
    estado_rotacion = models.CharField(max_length=20, choices=ESTADO_CHOICES)

    class Meta:
        db_table = 'turno_maquina'

    def save(self, *args, **kwargs):
        from datetime import datetime, timedelta

        # Si no hay horas, evitar llamar a datetime.combine con None
        if not self.hora_inicio or not self.hora_fin:
            # No se puede calcular, dejar en 0.00
            try:
                self.horas_trabajadas_calc = Decimal('0')
            except Exception:
                self.horas_trabajadas_calc = 0
            return super().save(*args, **kwargs)

        # Ambos tiempos presentes, calcular horas trabajadas
        inicio = datetime.combine(datetime.today(), self.hora_inicio)
        fin = datetime.combine(datetime.today(), self.hora_fin)
        
        if fin < inicio:
            fin += timedelta(days=1)
        
        diff = fin - inicio
        self.horas_trabajadas_calc = Decimal(str(diff.total_seconds() / 3600))
        super().save(*args, **kwargs)

class TurnoComplemento(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name='complementos')
    sondaje = models.ForeignKey(Sondaje, on_delete=models.PROTECT, null=True, blank=True, related_name='complementos_turno')
    tipo_complemento = models.ForeignKey(TipoComplemento, on_delete=models.PROTECT)
    codigo_serie = models.CharField(max_length=100)
    metros_inicio = models.DecimalField(max_digits=8, decimal_places=2)
    metros_fin = models.DecimalField(max_digits=8, decimal_places=2)
    metros_turno_calc = models.DecimalField(max_digits=8, decimal_places=2, editable=False)

    class Meta:
        db_table = 'turno_complemento'

    def save(self, *args, **kwargs):
        self.metros_turno_calc = self.metros_fin - self.metros_inicio
        super().save(*args, **kwargs)

class TurnoAditivo(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name='aditivos')
    sondaje = models.ForeignKey(Sondaje, on_delete=models.PROTECT, null=True, blank=True, related_name='aditivos_turno')
    tipo_aditivo = models.ForeignKey(TipoAditivo, on_delete=models.PROTECT)
    cantidad_usada = models.DecimalField(max_digits=8, decimal_places=2)
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT)

    class Meta:
        db_table = 'turno_aditivo'

class TurnoCorrida(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name='corridas')
    corrida_numero = models.PositiveIntegerField()
    desde = models.DecimalField(max_digits=8, decimal_places=2)
    hasta = models.DecimalField(max_digits=8, decimal_places=2)
    total_calc = models.DecimalField(max_digits=8, decimal_places=2, editable=False)
    longitud_testigo = models.DecimalField(max_digits=8, decimal_places=2)
    pct_recuperacion = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))])
    pct_retorno_agua = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))])
    litologia = models.TextField()

    class Meta:
        db_table = 'turno_corrida'
        unique_together = ['turno', 'corrida_numero']

    def save(self, *args, **kwargs):
        self.total_calc = self.hasta - self.desde
        super().save(*args, **kwargs)

class TurnoActividad(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name='actividades')
    actividad = models.ForeignKey(TipoActividad, on_delete=models.PROTECT)
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)  
    tiempo_calc = models.DecimalField(max_digits=4, decimal_places=2, editable=False)
    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = 'turno_actividad'

    def save(self, *args, **kwargs):
        from datetime import datetime, timedelta

        # Manejar casos donde las horas no estén completas
        if not self.hora_inicio or not self.hora_fin:
            try:
                self.tiempo_calc = Decimal('0')
            except Exception:
                self.tiempo_calc = 0
            return super().save(*args, **kwargs)

        inicio = datetime.combine(datetime.today(), self.hora_inicio)
        fin = datetime.combine(datetime.today(), self.hora_fin)

        if fin < inicio:
            fin += timedelta(days=1)

        diff = fin - inicio
        self.tiempo_calc = Decimal(str(diff.total_seconds() / 3600))
        super().save(*args, **kwargs)

class Abastecimiento(models.Model):
    FAMILIA_CHOICES = [
        ('PRODUCTOS_DIAMANTADOS', 'Productos Diamantados'),
        ('ADITIVOS_PERFORACION', 'Aditivos de Perforación'),
        ('CONSUMIBLES', 'Consumibles'),
        ('REPUESTOS', 'Repuestos'),
    ]
    
    mes = models.CharField(max_length=20)
    fecha = models.DateField()
    contrato = models.ForeignKey(Contrato, on_delete=models.PROTECT, related_name='abastecimientos')
    codigo_producto = models.CharField(max_length=50, blank=True)
    descripcion = models.TextField()
    familia = models.CharField(max_length=30, choices=FAMILIA_CHOICES)
    serie = models.CharField(max_length=50, blank=True, null=True)
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    tipo_complemento = models.ForeignKey(TipoComplemento, on_delete=models.PROTECT, null=True, blank=True)
    tipo_aditivo = models.ForeignKey(TipoAditivo, on_delete=models.PROTECT, null=True, blank=True)
    numero_guia = models.CharField(max_length=50, blank=True)
    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'abastecimiento'
        verbose_name = 'Abastecimiento'
        verbose_name_plural = 'Abastecimientos'
        ordering = ['-fecha', '-created_at']

    def save(self, *args, **kwargs):
        self.total = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.contrato.nombre_contrato} - {self.descripcion[:50]} ({self.fecha})"

class ConsumoStock(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name='consumos')
    abastecimiento = models.ForeignKey(Abastecimiento, on_delete=models.PROTECT)
    cantidad_consumida = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    serie_utilizada = models.CharField(max_length=50, blank=True)
    metros_inicio = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    metros_fin = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    metros_utilizados = models.DecimalField(max_digits=8, decimal_places=2, editable=False, null=True, blank=True)
    ESTADO_CHOICES = [
        ('OPTIMO', 'Óptimo'),
        ('BUENO', 'Bueno'),
        ('REGULAR', 'Regular'),
        ('DESGASTADO', 'Desgastado'),
        ('INUTILIZABLE', 'Inutilizable'),
    ]
    estado_final = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='OPTIMO')
    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'consumo_stock'
        verbose_name = 'Consumo de Stock'
        verbose_name_plural = 'Consumos de Stock'

    def save(self, *args, **kwargs):
        if self.metros_inicio and self.metros_fin:
            self.metros_utilizados = self.metros_fin - self.metros_inicio
        super().save(*args, **kwargs)