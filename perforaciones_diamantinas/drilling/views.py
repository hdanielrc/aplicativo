import json
from decimal import Decimal
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.db import transaction, models
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator
from .models import *
from .mixins import AdminOrContractFilterMixin, SystemAdminRequiredMixin
from .forms import *
from .utils.excel_importer import AbastecimientoExcelImporter

from datetime import datetime, time, timedelta
import json

def convert_to_time(value):
    """Convierte 'HH:MM' o 'HH:MM:SS' a time, o devuelve None si está vacío o inválido."""
    if not value:
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        parts = s.split(':')
        try:
            h = int(parts[0]); m = int(parts[1]) if len(parts) > 1 else 0; s_ = int(parts[2]) if len(parts) > 2 else 0
            return time(h, m, s_)
        except Exception:
            return None
    return None

# ===============================
# AUTHENTICATION VIEWS
# ===============================

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Credenciales incorrectas o usuario inactivo')
    return render(request, 'drilling/login.html')

@login_required
def user_logout(request):
    logout(request)
    return redirect('login')

# ===============================
# DASHBOARD
# ===============================
@login_required
def dashboard(request):
    contract = request.user.contrato
    hoy = timezone.now().date()
    
    # Verificar que el usuario tenga contrato
    if not contract:
        from .models import Cliente, Contrato
        cliente, _ = Cliente.objects.get_or_create(nombre='Cliente Demo')
        contrato, _ = Contrato.objects.get_or_create(
            nombre_contrato='Sistema Principal',
            defaults={'cliente': cliente, 'duracion_turno': 8, 'estado': 'ACTIVO'}
        )
        request.user.contrato = contrato
        request.user.save()
        contract = contrato
    
    # Métricas del dashboard
    sondajes_activos = Sondaje.objects.filter(contrato=contract, estado='ACTIVO').count()
    turnos_hoy = Turno.objects.filter(sondajes__contrato=contract, fecha=hoy).count()
    
    metros_perforados_mes = TurnoAvance.objects.filter(
        turno__sondajes__contrato=contract,
        turno__fecha__month=hoy.month,
        turno__fecha__year=hoy.year
    ).aggregate(total=models.Sum('metros_perforados'))['total'] or 0
    
    maquinas_operativas = Maquina.objects.filter(contrato=contract, estado='OPERATIVO').count()
    
    # Últimos turnos
    # Ajustado para M2M: filtrar por sondajes__contrato y prefetch sondajes
    ultimos_turnos = Turno.objects.filter(
        sondajes__contrato=contract
    ).select_related('maquina', 'tipo_turno').prefetch_related('sondajes').order_by('-fecha').distinct()[:5]
    
    # Stock crítico - CONSULTA CORREGIDA
    try:
        stock_critico = []
        abastecimientos = Abastecimiento.objects.filter(contrato=contract)
        
        for abastecimiento in abastecimientos[:10]:  # Limitar a 10 para performance
            total_consumido = ConsumoStock.objects.filter(
                abastecimiento=abastecimiento
            ).aggregate(
                total=models.Sum('cantidad_consumida')
            )['total'] or 0
            
            disponible = abastecimiento.cantidad - total_consumido
            
            if disponible <= 5:  # Stock crítico
                stock_critico.append({
                    'descripcion': abastecimiento.descripcion,
                    'disponible': disponible,
                    'unidad_medida': abastecimiento.unidad_medida,
                })
        
        # Ordenar por stock más crítico
        stock_critico = sorted(stock_critico, key=lambda x: x['disponible'])[:10]
        
    except Exception as e:
        print(f"Error en stock crítico: {e}")
        stock_critico = []
    
    context = {
        'contract': contract,
        'is_system_admin': request.user.can_manage_all_contracts(),
        'sondajes_activos': sondajes_activos,
        'turnos_hoy': turnos_hoy,
        'metros_perforados_mes': metros_perforados_mes,
        'maquinas_operativas': maquinas_operativas,
        'ultimos_turnos': ultimos_turnos,
        'stock_critico': stock_critico,
    }
    
    return render(request, 'drilling/dashboard.html', context)

# ===============================
# TRABAJADOR VIEWS - CRUD COMPLETO
# ===============================

class TrabajadorListView(AdminOrContractFilterMixin, ListView):
    model = Trabajador
    template_name = 'drilling/trabajadores/list.html'
    context_object_name = 'trabajadores'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().order_by('id')
        
        # Filtros adicionales
        cargo = self.request.GET.get('cargo')
        if cargo:
            queryset = queryset.filter(cargo=cargo)
            
        activo = self.request.GET.get('activo')
        if activo:
            queryset = queryset.filter(is_active=activo == 'true')
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cargos'] = Trabajador.CARGO_CHOICES
        context['filtros'] = self.request.GET
        return context

class TrabajadorCreateView(AdminOrContractFilterMixin, CreateView):
    model = Trabajador
    form_class = TrabajadorForm
    template_name = 'drilling/trabajadores/form.html'
    success_url = reverse_lazy('trabajador-list')

    def form_valid(self, form):
        if not self.request.user.can_manage_all_contracts():
            form.instance.contrato = self.request.user.contrato
        form.instance.is_active = True
        messages.success(self.request, 'Trabajador creado exitosamente')
        return super().form_valid(form)

class TrabajadorUpdateView(AdminOrContractFilterMixin, UpdateView):
    model = Trabajador
    form_class = TrabajadorForm
    template_name = 'drilling/trabajadores/form.html'
    success_url = reverse_lazy('trabajador-list')

    def form_valid(self, form):
        messages.success(self.request, 'Trabajador actualizado exitosamente')
        return super().form_valid(form)

class TrabajadorDeleteView(AdminOrContractFilterMixin, DeleteView):
    model = Trabajador
    template_name = 'drilling/trabajadores/confirm_delete.html'
    success_url = reverse_lazy('trabajador-list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Trabajador eliminado exitosamente')
        return super().delete(request, *args, **kwargs)

# ===============================
# MAQUINA VIEWS - CRUD COMPLETO
# ===============================

class MaquinaListView(AdminOrContractFilterMixin, ListView):
    model = Maquina
    template_name = 'drilling/maquinas/list.html'
    context_object_name = 'maquinas'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().order_by('nombre')
        
        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['estados'] = Maquina.ESTADO_CHOICES
        context['filtros'] = self.request.GET
        return context

class MaquinaCreateView(AdminOrContractFilterMixin, CreateView):
    model = Maquina
    form_class = MaquinaForm
    template_name = 'drilling/maquinas/form.html'
    success_url = reverse_lazy('maquina-list')

    def form_valid(self, form):
        if not self.request.user.can_manage_all_contracts():
            form.instance.contrato = self.request.user.contrato
        messages.success(self.request, 'Máquina creada exitosamente')
        return super().form_valid(form)

class MaquinaUpdateView(AdminOrContractFilterMixin, UpdateView):
    model = Maquina
    form_class = MaquinaForm
    template_name = 'drilling/maquinas/form.html'
    success_url = reverse_lazy('maquina-list')

    def form_valid(self, form):
        messages.success(self.request, 'Máquina actualizada exitosamente')
        return super().form_valid(form)

class MaquinaDeleteView(AdminOrContractFilterMixin, DeleteView):
    model = Maquina
    template_name = 'drilling/maquinas/confirm_delete.html'
    success_url = reverse_lazy('maquina-list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Máquina eliminada exitosamente')
        return super().delete(request, *args, **kwargs)

# ===============================
# SONDAJE VIEWS - CRUD COMPLETO
# ===============================

class SondajeListView(AdminOrContractFilterMixin, ListView):
    model = Sondaje
    template_name = 'drilling/sondajes/list.html'
    context_object_name = 'sondajes'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related('contrato').order_by('-fecha_inicio')
        
        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['estados'] = Sondaje.ESTADO_CHOICES
        context['filtros'] = self.request.GET
        return context

class SondajeCreateView(AdminOrContractFilterMixin, CreateView):
    model = Sondaje
    form_class = SondajeForm
    template_name = 'drilling/sondajes/form.html'
    success_url = reverse_lazy('sondaje-list')

    def form_valid(self, form):
        if not self.request.user.can_manage_all_contracts():
            form.instance.contrato = self.request.user.contrato
        messages.success(self.request, 'Sondaje creado exitosamente')
        return super().form_valid(form)

class SondajeUpdateView(AdminOrContractFilterMixin, UpdateView):
    model = Sondaje
    form_class = SondajeForm
    template_name = 'drilling/sondajes/form.html'
    success_url = reverse_lazy('sondaje-list')

    def form_valid(self, form):
        messages.success(self.request, 'Sondaje actualizado exitosamente')
        return super().form_valid(form)

class SondajeDeleteView(AdminOrContractFilterMixin, DeleteView):
    model = Sondaje
    template_name = 'drilling/sondajes/confirm_delete.html'
    success_url = reverse_lazy('sondaje-list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Sondaje eliminado exitosamente')
        return super().delete(request, *args, **kwargs)

# ===============================
# TIPO ACTIVIDAD VIEWS - CRUD COMPLETO
# ===============================

class TipoActividadListView(AdminOrContractFilterMixin, ListView):
    model = TipoActividad
    template_name = 'drilling/actividades/list.html'
    context_object_name = 'actividades'
    paginate_by = 20

class TipoActividadCreateView(AdminOrContractFilterMixin, CreateView):
    model = TipoActividad
    form_class = TipoActividadForm
    template_name = 'drilling/actividades/form.html'
    success_url = reverse_lazy('actividades-list')

    def form_valid(self, form):
        messages.success(self.request, 'Actividad creada exitosamente')
        return super().form_valid(form)

class TipoActividadUpdateView(AdminOrContractFilterMixin, UpdateView):
    model = TipoActividad
    form_class = TipoActividadForm
    template_name = 'drilling/actividades/form.html'
    success_url = reverse_lazy('actividades-list')

    def form_valid(self, form):
        messages.success(self.request, 'Actividad actualizada exitosamente')
        return super().form_valid(form)

class TipoActividadDeleteView(AdminOrContractFilterMixin, DeleteView):
    model = TipoActividad
    template_name = 'drilling/actividades/confirm_delete.html'
    success_url = reverse_lazy('actividades-list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Actividad eliminada exitosamente')
        return super().delete(request, *args, **kwargs)


class ContratoActividadesUpdateView(SystemAdminRequiredMixin, TemplateView):
    """Vista para asignar/desasignar actividades (maestro) a un contrato.
    Solo los admins del sistema pueden gestionar esto; contract managers deberán
    usar su propia sección para ver las actividades asignadas.
    """
    template_name = 'drilling/contratos/actividades_form.html'

    def get(self, request, pk):
        contrato = get_object_or_404(Contrato, pk=pk)
        actividades = TipoActividad.objects.all().order_by('nombre')
        context = {
            'contrato': contrato,
            'actividades': actividades,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        contrato = get_object_or_404(Contrato, pk=pk)
        actividad_ids = request.POST.getlist('actividades')
        actividades = TipoActividad.objects.filter(id__in=actividad_ids)
        contrato.actividades.set(actividades)
        messages.success(request, 'Actividades asignadas al contrato correctamente')
        return redirect('contrato-actividades', pk=contrato.pk)

# ===============================
# TIPO TURNO VIEWS - CRUD COMPLETO
# ===============================

class TipoTurnoListView(AdminOrContractFilterMixin, ListView):
    model = TipoTurno
    template_name = 'drilling/tipo_turnos/list.html'
    context_object_name = 'tipos_turno'
    paginate_by = 20

class TipoTurnoCreateView(AdminOrContractFilterMixin, CreateView):
    model = TipoTurno
    form_class = TipoTurnoForm
    template_name = 'drilling/tipo_turnos/form.html'
    success_url = reverse_lazy('tipo-turno-list')

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de turno creado exitosamente')
        return super().form_valid(form)

class TipoTurnoUpdateView(AdminOrContractFilterMixin, UpdateView):
    model = TipoTurno
    form_class = TipoTurnoForm
    template_name = 'drilling/tipo_turnos/form.html'
    success_url = reverse_lazy('tipo-turno-list')

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de turno actualizado exitosamente')
        return super().form_valid(form)

class TipoTurnoDeleteView(AdminOrContractFilterMixin, DeleteView):
    model = TipoTurno
    template_name = 'drilling/tipo_turnos/confirm_delete.html'
    success_url = reverse_lazy('tipo-turno-list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Tipo de turno eliminado exitosamente')
        return super().delete(request, *args, **kwargs)

# ===============================
# TIPO COMPLEMENTO VIEWS - CRUD COMPLETO
# ===============================

class TipoComplementoListView(AdminOrContractFilterMixin, ListView):
    model = TipoComplemento
    template_name = 'drilling/complementos/list.html'
    context_object_name = 'complementos'
    paginate_by = 20

class TipoComplementoCreateView(AdminOrContractFilterMixin, CreateView):
    model = TipoComplemento
    form_class = TipoComplementoForm
    template_name = 'drilling/complementos/form.html'
    success_url = reverse_lazy('complemento-list')

    def form_valid(self, form):
        messages.success(self.request, 'Complemento creado exitosamente')
        return super().form_valid(form)

class TipoComplementoUpdateView(AdminOrContractFilterMixin, UpdateView):
    model = TipoComplemento
    form_class = TipoComplementoForm
    template_name = 'drilling/complementos/form.html'
    success_url = reverse_lazy('complemento-list')

    def form_valid(self, form):
        messages.success(self.request, 'Complemento actualizado exitosamente')
        return super().form_valid(form)

class TipoComplementoDeleteView(AdminOrContractFilterMixin, DeleteView):
    model = TipoComplemento
    template_name = 'drilling/complementos/confirm_delete.html'
    success_url = reverse_lazy('complemento-list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Complemento eliminado exitosamente')
        return super().delete(request, *args, **kwargs)

# ===============================
# TIPO ADITIVO VIEWS - CRUD COMPLETO
# ===============================

class TipoAditivoListView(AdminOrContractFilterMixin, ListView):
    model = TipoAditivo
    template_name = 'drilling/aditivos/list.html'
    context_object_name = 'aditivos'
    paginate_by = 20

class TipoAditivoCreateView(AdminOrContractFilterMixin, CreateView):
    model = TipoAditivo
    form_class = TipoAditivoForm
    template_name = 'drilling/aditivos/form.html'
    success_url = reverse_lazy('aditivo-list')

    def form_valid(self, form):
        messages.success(self.request, 'Aditivo creado exitosamente')
        return super().form_valid(form)

class TipoAditivoUpdateView(AdminOrContractFilterMixin, UpdateView):
    model = TipoAditivo
    form_class = TipoAditivoForm
    template_name = 'drilling/aditivos/form.html'
    success_url = reverse_lazy('aditivo-list')

    def form_valid(self, form):
        messages.success(self.request, 'Aditivo actualizado exitosamente')
        return super().form_valid(form)

class TipoAditivoDeleteView(AdminOrContractFilterMixin, DeleteView):
    model = TipoAditivo
    template_name = 'drilling/aditivos/confirm_delete.html'
    success_url = reverse_lazy('aditivo-list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Aditivo eliminado exitosamente')
        return super().delete(request, *args, **kwargs)

# ===============================
# UNIDAD MEDIDA VIEWS - CRUD COMPLETO
# ===============================

class UnidadMedidaListView(AdminOrContractFilterMixin, ListView):
    model = UnidadMedida
    template_name = 'drilling/unidades/list.html'
    context_object_name = 'unidades'
    paginate_by = 20

class UnidadMedidaCreateView(AdminOrContractFilterMixin, CreateView):
    model = UnidadMedida
    form_class = UnidadMedidaForm
    template_name = 'drilling/unidades/form.html'
    success_url = reverse_lazy('unidad-list')

    def form_valid(self, form):
        messages.success(self.request, 'Unidad de medida creada exitosamente')
        return super().form_valid(form)

class UnidadMedidaUpdateView(AdminOrContractFilterMixin, UpdateView):
    model = UnidadMedida
    form_class = UnidadMedidaForm
    template_name = 'drilling/unidades/form.html'
    success_url = reverse_lazy('unidad-list')

    def form_valid(self, form):
        messages.success(self.request, 'Unidad de medida actualizada exitosamente')
        return super().form_valid(form)

class UnidadMedidaDeleteView(AdminOrContractFilterMixin, DeleteView):
    model = UnidadMedida
    template_name = 'drilling/unidades/confirm_delete.html'
    success_url = reverse_lazy('unidad-list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Unidad de medida eliminada exitosamente')
        return super().delete(request, *args, **kwargs)

# ===============================
# TURNO VIEWS - COMPLETO Y AVANZADO
# ===============================

from datetime import datetime, time
import json
from django.db import transaction
from django.contrib import messages
from django.shortcuts import render, redirect

@login_required
def crear_turno_completo(request, pk=None):
    if not request.user.can_supervise_operations():
        messages.error(request, "Acceso denegado. Requiere permisos de Supervisor o superior.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            # Obtener datos básicos del turno
            # soporte para múltiples sondajes: 'sondajes' (multiselect) o 'sondaje' (compatibilidad)
            sondaje_ids = request.POST.getlist('sondajes') or []
            if not sondaje_ids:
                single = request.POST.get('sondaje')
                if single:
                    sondaje_ids = [single]
            maquina_id = request.POST.get('maquina')
            tipo_turno_id = request.POST.get('tipo_turno')
            fecha = request.POST.get('fecha')
            
            # Validar campos requeridos
            if not sondaje_ids or not all([maquina_id, tipo_turno_id, fecha]):
                messages.error(request, "Faltan campos requeridos: sondaje(s), máquina, tipo de turno y fecha.")
                return redirect('crear-turno-completo')

            # Obtener objetos relacionados EN EL MISMO ORDEN en que fueron seleccionados
            sondajes_list = []
            try:
                for sid in sondaje_ids:
                    sondajes_list.append(Sondaje.objects.get(id=int(sid)))
            except (ValueError, Sondaje.DoesNotExist):
                messages.error(request, 'Sondaje(s) seleccionado(s) inválido(s)')
                return redirect('crear-turno-completo')
            # Para compatibilidad con el código existente que usa una única variable 'sondaje',
            # tomamos el primero para lecturas puntuales (duración, contrato) y mantenemos la lista
            sondaje = sondajes_list[0]
            maquina = Maquina.objects.get(id=maquina_id)
            tipo_turno = TipoTurno.objects.get(id=tipo_turno_id)
            
            # Verificar permisos de contrato: todos los sondajes deben pertenecer al mismo contrato
            contratos_ids = set([s.contrato_id for s in sondajes_list])
            if len(contratos_ids) > 1:
                messages.error(request, 'Los sondajes seleccionados pertenecen a contratos diferentes.')
                return redirect('crear-turno-completo')
            contrato_sondajes = sondajes_list[0].contrato
            if not request.user.can_manage_all_contracts() and contrato_sondajes != request.user.contrato:
                messages.error(request, "No tiene permisos para crear turnos en este contrato.")
                return redirect('dashboard')
            
            # Parsear y validar datos complejos ANTES de abrir la transacción
            # Esto evita abrir la transacción si los datos están corruptos
            trabajadores_parsed = []
            complementos_parsed = []
            aditivos_parsed = []
            actividades_parsed = []
            corridas_parsed = []
            metros_perforados_val = None

            # Trabajadores
            trabajadores_data = request.POST.get('trabajadores')
            if trabajadores_data:
                try:
                    trabajadores_raw = json.loads(trabajadores_data)
                    for t in trabajadores_raw:
                        if 'trabajador_id' not in t or 'funcion' not in t:
                            messages.warning(request, 'Trabajador con datos incompletos será omitido')
                            continue
                        trabajadores_parsed.append({
                            'trabajador_id': t['trabajador_id'],
                            'funcion': t['funcion'],
                            'observaciones': t.get('observaciones', '')
                        })
                except json.JSONDecodeError as e:
                    messages.error(request, f'JSON inválido en trabajadores: {e}')
                    return redirect('crear-turno-completo')

            # Complementos
            complementos_data = request.POST.get('complementos')
            if complementos_data:
                try:
                    complementos_raw = json.loads(complementos_data)
                    for c in complementos_raw:
                        try:
                            complementos_parsed.append({
                                'tipo_complemento_id': int(c['tipo_complemento_id']),
                                'codigo_serie': c.get('codigo_serie', ''),
                                'metros_inicio': float(c['metros_inicio']),
                                'metros_fin': float(c['metros_fin']),
                                'sondaje_id': int(c.get('sondaje_id')) if c.get('sondaje_id') else None,
                            })
                        except (KeyError, ValueError):
                            messages.warning(request, 'Complemento con datos inválidos será omitido')
                except json.JSONDecodeError as e:
                    messages.error(request, f'JSON inválido en complementos: {e}')
                    return redirect('crear-turno-completo')

            # Aditivos
            aditivos_data = request.POST.get('aditivos')
            if aditivos_data:
                try:
                    aditivos_raw = json.loads(aditivos_data)
                    for a in aditivos_raw:
                        try:
                            aditivos_parsed.append({
                                'tipo_aditivo_id': int(a['tipo_aditivo_id']),
                                'cantidad_usada': float(a['cantidad_usada']),
                                'unidad_medida_id': int(a['unidad_medida_id']),
                                'sondaje_id': int(a.get('sondaje_id')) if a.get('sondaje_id') else None,
                            })
                        except (KeyError, ValueError):
                            messages.warning(request, 'Aditivo con datos inválidos será omitido')
                except json.JSONDecodeError as e:
                    messages.error(request, f'JSON inválido en aditivos: {e}')
                    return redirect('crear-turno-completo')

            # Actividades
            actividades_data = request.POST.get('actividades')
            if actividades_data:
                try:
                    actividades_raw = json.loads(actividades_data)
                    for act in actividades_raw:
                        try:
                            actividades_parsed.append({
                                'actividad_id': int(act['actividad_id']),
                                'hora_inicio': convert_to_time(act.get('hora_inicio')),
                                'hora_fin': convert_to_time(act.get('hora_fin')),
                                'observaciones': act.get('observaciones', '')
                            })
                        except (KeyError, ValueError):
                            messages.warning(request, 'Actividad con datos inválidos será omitida')
                except json.JSONDecodeError as e:
                    messages.error(request, f'JSON inválido en actividades: {e}')
                    return redirect('crear-turno-completo')

            # Corridas
            corridas_data = request.POST.get('corridas')
            if corridas_data:
                try:
                    corridas_raw = json.loads(corridas_data)
                    for cr in corridas_raw:
                        try:
                            corridas_parsed.append({
                                'corrida_numero': int(cr['corrida_numero']),
                                'desde': float(cr['desde']),
                                'hasta': float(cr['hasta']),
                                'longitud_testigo': float(cr['longitud_testigo']),
                                'pct_recuperacion': float(cr['pct_recuperacion']),
                                'pct_retorno_agua': float(cr['pct_retorno_agua']),
                                'litologia': cr.get('litologia', '')
                            })
                        except (KeyError, ValueError):
                            messages.warning(request, 'Corrida con datos inválidos será omitida')
                except json.JSONDecodeError as e:
                    messages.error(request, f'JSON inválido en corridas: {e}')
                    return redirect('crear-turno-completo')

            # Metrajes por sondaje: preferimos la lista de metrajes por sondaje
            # que viene en el formulario (name='sondajes_metraje'). Sumaremos
            # esos valores y los usaremos como avance total del turno.
            metrajes_raw = request.POST.getlist('sondajes_metraje') or []
            if not metrajes_raw:
                single_m = request.POST.get('sondaje_metraje')
                if single_m:
                    metrajes_raw = [single_m]

            metros_perforados_val = None
            if metrajes_raw:
                try:
                    total_m = 0.0
                    for mv in metrajes_raw:
                        if mv in [None, '']:
                            continue
                        total_m += float(mv)
                    metros_perforados_val = total_m
                except ValueError:
                    # Si algún valor no es numérico, ignoramos el avance calculado
                    messages.warning(request, 'Algunos metrajes por sondaje no son numéricos; avance será 0 o calculado desde TurnoSondaje')

            # Procesar datos de máquina: aceptamos lecturas de horómetro (numéricas)
            # o tiempos en formato HH:MM. Si el valor es numérico será tratado como
            # lectura de horómetro (horometro_inicio/horometro_fin).
            hora_inicio_maq = request.POST.get('hora_inicio_maq')
            hora_fin_maq = request.POST.get('hora_fin_maq')
            hora_inicio_maq_parsed = None
            hora_fin_maq_parsed = None
            horometro_inicio_val = None
            horometro_fin_val = None
            # Intentar parsear como Decimal (horómetro)
            from decimal import Decimal, InvalidOperation
            try:
                if hora_inicio_maq is not None and hora_inicio_maq.strip() != '':
                    try:
                        horometro_inicio_val = Decimal(hora_inicio_maq)
                    except Exception:
                        hora_inicio_maq_parsed = convert_to_time(hora_inicio_maq)
                if hora_fin_maq is not None and hora_fin_maq.strip() != '':
                    try:
                        horometro_fin_val = Decimal(hora_fin_maq)
                    except Exception:
                        hora_fin_maq_parsed = convert_to_time(hora_fin_maq)
            except Exception:
                # En caso de cualquier error, fallback a tratar como time strings
                hora_inicio_maq_parsed = convert_to_time(hora_inicio_maq) if hora_inicio_maq else None
                hora_fin_maq_parsed = convert_to_time(hora_fin_maq) if hora_fin_maq else None

            # ----------------------------------
            # VALIDACIÓN: sumar horas de actividades
            # ----------------------------------
            try:
                total_horas_post = 0.0
                for a in actividades_parsed:
                    hi = a.get('hora_inicio')
                    hf = a.get('hora_fin')
                    if hi and hf:
                        # hi/hf are time objects (convert_to_time)
                        start_dt = datetime.combine(datetime.today().date(), hi)
                        end_dt = datetime.combine(datetime.today().date(), hf)
                        if end_dt < start_dt:
                            end_dt = end_dt + timedelta(days=1)
                        total_horas_post += (end_dt - start_dt).total_seconds() / 3600.0
                # Prefer the current user's contrato.duracion_turno for non-admin users
                if request.user.can_manage_all_contracts():
                    duracion_esperada = float(sondaje.contrato.duracion_turno or 0)
                else:
                    duracion_esperada = float(getattr(request.user.contrato, 'duracion_turno', 0) or 0)
                if duracion_esperada > 0 and total_horas_post < duracion_esperada:
                    faltan = duracion_esperada - total_horas_post
                    # También incluir el valor de duración en el contrato del usuario por si hay discrepancias
                    try:
                        usuario_duracion = float(request.user.contrato.duracion_turno or 0)
                    except Exception:
                        usuario_duracion = None
                    msg = (f'Faltan horas al turno: se han registrado {total_horas_post:.2f}h, '
                           f'se requieren {duracion_esperada:.2f}h (faltan {faltan:.2f}h).')
                    if usuario_duracion is not None:
                        msg += f' [duración contrato sondaje={duracion_esperada:.2f}h, duración contrato usuario={usuario_duracion:.2f}h]'
                    messages.error(request, msg)
                    # Volver a renderizar el formulario con los datos pre-llenados
                    context = get_context_data(request)
                    import json as _json
                    context.update({
                        'edit_mode': True,
                        'edit_trabajadores_json': _json.dumps(trabajadores_parsed),
                        'edit_complementos_json': _json.dumps(complementos_parsed),
                        'edit_aditivos_json': _json.dumps(aditivos_parsed),
                        'edit_actividades_json': _json.dumps([
                            {
                                'actividad_id': a['actividad_id'],
                                'hora_inicio': a['hora_inicio'].isoformat() if a.get('hora_inicio') else '',
                                'hora_fin': a['hora_fin'].isoformat() if a.get('hora_fin') else '',
                                'observaciones': a.get('observaciones', '')
                            } for a in actividades_parsed
                        ]),
                        'edit_corridas_json': _json.dumps(corridas_parsed),
                        # pasar lista de sondajes para que la plantilla preseleccione
                        'edit_sondaje_ids': _json.dumps([int(x) for x in sondaje_ids]) if sondaje_ids else _json.dumps([]),
                        'edit_sondaje_id': int(sondaje_ids[0]) if sondaje_ids else None,
                        'edit_maquina_id': int(maquina_id) if maquina_id else None,
                        'edit_tipo_turno_id': int(tipo_turno_id) if tipo_turno_id else None,
                        'edit_fecha': fecha,
                            # Si hubo metrajes en POST, ofrecer la suma; si no, 0
                            'edit_metros_perforados': (metros_perforados_val or 0),
                        'edit_hora_inicio_maq': hora_inicio_maq_parsed.isoformat() if hora_inicio_maq_parsed else '',
                        'edit_hora_fin_maq': hora_fin_maq_parsed.isoformat() if hora_fin_maq_parsed else '',
                        'edit_estado_bomba': request.POST.get('estado_bomba', ''),
                        'edit_estado_unidad': request.POST.get('estado_unidad', ''),
                        'edit_estado_rotacion': request.POST.get('estado_rotacion', ''),
                    })
                    return render(request, 'drilling/turno/crear_completo.html', context)
            except Exception:
                # Si falla la validación por cualquier razón, seguimos con el flujo
                pass

            # Ahora que todo está parseado/validado, crear o actualizar registros en una transacción
            with transaction.atomic():
                if pk:
                    # Editar turno existente
                    turno = get_object_or_404(Turno, pk=pk)
                    turno.maquina = maquina
                    turno.tipo_turno = tipo_turno
                    turno.fecha = fecha
                    turno.contrato = contrato_sondajes
                    turno.save()
                    # actualizar asociaciones many-to-many de sondajes
                    try:
                        # Usar un savepoint (atomic anidado) para que si falla la asignación
                        # M2M no deje la transacción completa en estado roto.
                        with transaction.atomic():
                            turno.sondajes.set([s.id for s in sondajes_list])
                    except Exception:
                        # No bloquear el flujo por fallos en la asociación M2M; el savepoint
                        # asegura que la transacción externa no quede marcada como rollback.
                        pass

                    # Eliminar relaciones existentes y recrear desde los datos enviados
                    # También eliminar asociaciones TurnoSondaje para rehacer con metrajes
                    TurnoSondaje.objects.filter(turno=turno).delete()
                    TurnoMaquina.objects.filter(turno=turno).delete()
                    TurnoTrabajador.objects.filter(turno=turno).delete()
                    TurnoComplemento.objects.filter(turno=turno).delete()
                    TurnoAditivo.objects.filter(turno=turno).delete()
                    TurnoActividad.objects.filter(turno=turno).delete()
                    TurnoCorrida.objects.filter(turno=turno).delete()
                    TurnoAvance.objects.filter(turno=turno).delete()
                else:
                    # Crear el turno principal CON relación directa a contrato
                    turno = Turno.objects.create(
                        fecha=fecha,
                        contrato=contrato_sondajes,
                        maquina=maquina,
                        tipo_turno=tipo_turno,
                    )
                    # asignar sondajes seleccionados
                    try:
                        # Mismo tratamiento en la rama de creación: usar savepoint para M2M
                        with transaction.atomic():
                            turno.sondajes.set([s.id for s in sondajes_list])
                    except Exception:
                        pass

                # Guardar metrajes por sondaje si fueron enviados (usar metrajes_raw
                # ya parseados arriba). Se espera una lista paralela 'sondajes_metraje'
                # en el POST
                from decimal import Decimal
                try:
                    # Asegurar que los pares (sondaje_id, metraje) respeten el orden de selección
                    pairs = list(zip([int(s.id) for s in sondajes_list], metrajes_raw)) if metrajes_raw else []
                    objs = []
                    if pairs:
                        for sid, m in pairs:
                            try:
                                metros_val = Decimal(str(m)) if m not in [None, ''] else Decimal('0')
                            except Exception:
                                metros_val = Decimal('0')
                            objs.append(TurnoSondaje(turno=turno, sondaje_id=sid, metros_turno=metros_val))
                        if objs:
                            # bulk_create en su propio savepoint para aislar errores
                            try:
                                with transaction.atomic():
                                    TurnoSondaje.objects.bulk_create(objs)
                            except Exception:
                                # No bloquear el flujo si falla la bulk_create; ya hay asociación M2M
                                pass
                    else:
                        # Si no se enviaron metrajes, asegurarse de que existan filas TurnoSondaje
                        # (la asignación M2M previa puede haber creado entradas con valores por defecto)
                        pass
                except Exception:
                    # No bloquear el flujo si algo falla al preparar metrajes; la transacción global seguirá intacta
                    pass

                # Crear TurnoMaquina si corresponde
                if hora_inicio_maq_parsed or hora_fin_maq_parsed or horometro_inicio_val is not None or horometro_fin_val is not None or request.POST.get('estado_bomba'):
                    # Si estamos editando (pk) y existía un TurnoMaquina previo, restar sus horas del horometro
                    if pk:
                        prev_tm = TurnoMaquina.objects.filter(turno=turno).first()
                        if prev_tm and prev_tm.horas_trabajadas_calc:
                            try:
                                maquina.horometro = maquina.horometro - prev_tm.horas_trabajadas_calc
                                maquina.save(update_fields=['horometro'])
                            except Exception:
                                # No bloquear el flujo si falla la resta
                                pass

                    tm = TurnoMaquina.objects.create(
                        turno=turno,
                        hora_inicio=hora_inicio_maq_parsed,
                        hora_fin=hora_fin_maq_parsed,
                        horometro_inicio=horometro_inicio_val,
                        horometro_fin=horometro_fin_val,
                        estado_bomba=request.POST.get('estado_bomba', 'OPERATIVO'),
                        estado_unidad=request.POST.get('estado_unidad', 'OPERATIVO'),
                        estado_rotacion=request.POST.get('estado_rotacion', 'OPERATIVO')
                    )

                    # Después de crear TurnoMaquina, su save() habrá calculado horas_trabajadas_calc.
                    # Sumar ese valor al horómetro de la máquina asociada.
                    try:
                        if tm.horas_trabajadas_calc:
                            # usar Decimal para mantener precisión
                            from decimal import Decimal
                            incremento = Decimal(tm.horas_trabajadas_calc)
                            # Actualizar horómetro en un savepoint para evitar marcar la transacción si falla
                            try:
                                with transaction.atomic():
                                    maquina.horometro = (maquina.horometro or Decimal('0')) + incremento
                                    maquina.save(update_fields=['horometro'])
                            except Exception:
                                # No bloquear el flujo si falla la suma al horómetro
                                pass
                    except Exception:
                        # No bloquear el flujo si hay problemas con el cálculo
                        pass

                # Crear trabajadores: resolver por `dni` (la plantilla envía el dni como valor)
                for t in trabajadores_parsed:
                    try:
                        trabajador_obj = Trabajador.objects.get(dni=str(t['trabajador_id']))
                    except Trabajador.DoesNotExist:
                        # Omitir si el trabajador no existe (no bloquear la transacción)
                        continue
                    TurnoTrabajador.objects.create(
                        turno=turno,
                        trabajador=trabajador_obj,
                        funcion=t['funcion'],
                        observaciones=t['observaciones']
                    )

                # Crear complementos
                for c in complementos_parsed:
                    TurnoComplemento.objects.create(
                        turno=turno,
                        tipo_complemento_id=c['tipo_complemento_id'],
                        codigo_serie=c['codigo_serie'],
                        metros_inicio=c['metros_inicio'],
                        metros_fin=c['metros_fin'],
                        sondaje_id=c.get('sondaje_id')
                    )

                # Crear aditivos
                for a in aditivos_parsed:
                    TurnoAditivo.objects.create(
                        turno=turno,
                        tipo_aditivo_id=a['tipo_aditivo_id'],
                        cantidad_usada=a['cantidad_usada'],
                        unidad_medida_id=a['unidad_medida_id'],
                        sondaje_id=a.get('sondaje_id')
                    )

                # Crear actividades
                for act in actividades_parsed:
                    TurnoActividad.objects.create(
                        turno=turno,
                        actividad_id=act['actividad_id'],
                        hora_inicio=act['hora_inicio'],
                        hora_fin=act['hora_fin'],
                        observaciones=act['observaciones']
                    )

                # Crear corridas
                for cr in corridas_parsed:
                    TurnoCorrida.objects.create(
                        turno=turno,
                        corrida_numero=cr['corrida_numero'],
                        desde=cr['desde'],
                        hasta=cr['hasta'],
                        longitud_testigo=cr['longitud_testigo'],
                        pct_recuperacion=cr['pct_recuperacion'],
                        pct_retorno_agua=cr['pct_retorno_agua'],
                        litologia=cr['litologia']
                    )

                # Crear avance: preferimos sumar los metrajes guardados en TurnoSondaje
                # (si la bulk_create funcionó). Como fallback, usamos el valor sumado
                # recibido en POST (metros_perforados_val) si existe.
                try:
                    from django.db.models import Sum
                    total_db = TurnoSondaje.objects.filter(turno=turno).aggregate(total=Sum('metros_turno'))['total']
                    total_db = float(total_db) if total_db is not None else 0.0
                except Exception:
                    total_db = 0.0

                final_total_metros = total_db if total_db > 0 else (metros_perforados_val or 0)
                try:
                    if final_total_metros and float(final_total_metros) > 0:
                        TurnoAvance.objects.create(
                            turno=turno,
                            metros_perforados=final_total_metros
                        )
                except Exception:
                    # No bloquear el flujo si falla la creación del avance
                    pass

            if pk:
                messages.success(request, f'Turno #{turno.id} actualizado exitosamente para {sondaje.nombre_sondaje}')
            else:
                messages.success(request, f'Turno #{turno.id} creado exitosamente para {sondaje.nombre_sondaje}')
            # Después de crear/actualizar, verificar si las actividades suman la duración del turno
            try:
                # Sumar horas de actividades guardadas
                total_horas = 0
                for act_obj in TurnoActividad.objects.filter(turno=turno):
                    if act_obj.tiempo_calc:
                        total_horas += float(act_obj.tiempo_calc)
                # Obtener duración esperada desde el contrato del sondaje
                # Same logic as above: for non-admin users prefer their contrato.duracion_turno
                if request.user.can_manage_all_contracts():
                    duracion_esperada = float(sondaje.contrato.duracion_turno or 0)
                else:
                    duracion_esperada = float(getattr(request.user.contrato, 'duracion_turno', 0) or 0)
                if total_horas >= duracion_esperada and duracion_esperada > 0:
                    turno.estado = 'COMPLETADO'
                    turno.save(update_fields=['estado'])
            except Exception:
                # No bloquear el flujo si falla esta comprobación
                pass
            return redirect('listar-turnos')
            
        except Exception as e:
            messages.error(request, f'Error al crear turno: {str(e)}')
            return redirect('crear-turno-completo')
    
    # GET request - si es modo edición pre-popular datos
    context = get_context_data(request)
    if pk:
        turno = get_object_or_404(Turno, pk=pk)
        # preparar listas JSON para inyectar en template
        trabajadores = []
        for tt in TurnoTrabajador.objects.filter(turno=turno).select_related('trabajador'):
            trabajadores.append({
                # Serializar por DNI para que la plantilla pueda preseleccionar por value="dni"
                'trabajador_id': getattr(tt.trabajador, 'dni', None),
                'funcion': tt.funcion,
                'observaciones': tt.observaciones,
            })

        complementos = []
        for c in TurnoComplemento.objects.filter(turno=turno):
            complementos.append({
                'tipo_complemento_id': c.tipo_complemento_id,
                'codigo_serie': c.codigo_serie,
                'metros_inicio': float(c.metros_inicio),
                'metros_fin': float(c.metros_fin),
                'sondaje_id': c.sondaje_id,
            })

        aditivos = []
        for a in TurnoAditivo.objects.filter(turno=turno):
            aditivos.append({
                'tipo_aditivo_id': a.tipo_aditivo_id,
                'cantidad_usada': float(a.cantidad_usada),
                'unidad_medida_id': a.unidad_medida_id,
                'sondaje_id': a.sondaje_id,
            })

        actividades = []
        for act in TurnoActividad.objects.filter(turno=turno):
            actividades.append({
                'actividad_id': act.actividad_id,
                'hora_inicio': act.hora_inicio.isoformat() if act.hora_inicio else '',
                'hora_fin': act.hora_fin.isoformat() if act.hora_fin else '',
                'observaciones': act.observaciones,
            })

        corridas = []
        for cr in TurnoCorrida.objects.filter(turno=turno):
            corridas.append({
                'corrida_numero': cr.corrida_numero,
                'desde': float(cr.desde),
                'hasta': float(cr.hasta),
                'longitud_testigo': float(cr.longitud_testigo),
                'pct_recuperacion': float(cr.pct_recuperacion),
                'pct_retorno_agua': float(cr.pct_retorno_agua),
                'litologia': cr.litologia,
            })

        # Preferir sumar los metrajes guardados en TurnoSondaje para obtener el avance
        try:
            from django.db.models import Sum
            metros_sum = TurnoSondaje.objects.filter(turno=turno).aggregate(total=Sum('metros_turno'))['total']
            metros = float(metros_sum) if metros_sum is not None else 0
        except Exception:
            # Fallback a TurnoAvance si algo falla
            avance = TurnoAvance.objects.filter(turno=turno).first()
            metros = float(avance.metros_perforados) if avance else 0

        # añadir datos al contexto serializados
        import json as _json
        # Asegurar que el conjunto de tipos de actividad presente en la plantilla
        # incluya las actividades ya asociadas al turno (si las hubiera). Esto
        # evita que, al editar un turno, el <select> quede vacío si la actividad
        # no está asignada al contrato actual.
        try:
            actividad_ids = [int(a['actividad_id']) for a in actividades if a.get('actividad_id')]
            if actividad_ids:
                extra_qs = TipoActividad.objects.filter(id__in=actividad_ids)
                existing_qs = context.get('tipos_actividad')
                try:
                    context['tipos_actividad'] = (existing_qs | extra_qs).distinct()
                except Exception:
                    context['tipos_actividad'] = extra_qs
        except Exception:
            pass

        # Cuando exista lectura de horómetro, exponerla; si no, usar hora ISO para prefill
        _maquina_estado = getattr(turno, 'maquina_estado', None)
        edit_h_ini = ''
        edit_h_fin = ''
        try:
            if _maquina_estado and getattr(_maquina_estado, 'horometro_inicio', None) is not None:
                edit_h_ini = str(_maquina_estado.horometro_inicio)
            elif _maquina_estado and getattr(_maquina_estado, 'hora_inicio', None):
                edit_h_ini = _maquina_estado.hora_inicio.isoformat()
        except Exception:
            edit_h_ini = ''
        try:
            if _maquina_estado and getattr(_maquina_estado, 'horometro_fin', None) is not None:
                edit_h_fin = str(_maquina_estado.horometro_fin)
            elif _maquina_estado and getattr(_maquina_estado, 'hora_fin', None):
                edit_h_fin = _maquina_estado.hora_fin.isoformat()
        except Exception:
            edit_h_fin = ''

        context.update({
            'edit_mode': True,
            'edit_turno_id': turno.id,
            # Previously single sondaje id; now expose list of sondaje ids for the template
            'edit_sondaje_ids': list(turno.sondajes.values_list('id', flat=True)),
            # Lista de objetos {'id': sondaje_id, 'metros': metros_turno} para prellenado de metrajes
            'edit_sondajes_json': _json.dumps([
                {'id': ts.sondaje_id, 'metros': float(ts.metros_turno or 0)}
                for ts in TurnoSondaje.objects.filter(turno=turno)
            ]),
            'edit_maquina_id': turno.maquina_id,
            'edit_tipo_turno_id': turno.tipo_turno_id,
            'edit_fecha': turno.fecha.isoformat(),
            'edit_trabajadores_json': _json.dumps(trabajadores),
            'edit_complementos_json': _json.dumps(complementos),
            'edit_aditivos_json': _json.dumps(aditivos),
            'edit_actividades_json': _json.dumps(actividades),
            'edit_corridas_json': _json.dumps(corridas),
            'edit_metros_perforados': metros,
            'edit_hora_inicio_maq': edit_h_ini,
            'edit_hora_fin_maq': edit_h_fin,
            'edit_estado_bomba': getattr(getattr(turno, 'maquina_estado', None), 'estado_bomba', ''),
            'edit_estado_unidad': getattr(getattr(turno, 'maquina_estado', None), 'estado_unidad', ''),
            'edit_estado_rotacion': getattr(getattr(turno, 'maquina_estado', None), 'estado_rotacion', ''),
        })

    return render(request, 'drilling/turno/crear_completo.html', context)

def convert_to_time(time_str):
    """Convierte string de hora a objeto time"""
    if not time_str:
        return None
    
    try:
        # Si ya es un objeto time, devolverlo tal como está
        if isinstance(time_str, time):
            return time_str
            
        # Si es string, convertir
        if isinstance(time_str, str):
            # Formato HH:MM o HH:MM:SS
            time_parts = time_str.split(':')
            if len(time_parts) >= 2:
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                second = int(time_parts[2]) if len(time_parts) > 2 else 0
                return time(hour, minute, second)
        
        return None
    except (ValueError, AttributeError):
        return None

def get_context_data(request):
    """Obtener datos de contexto para el formulario"""
    contract = request.user.contrato
    
    if request.user.can_manage_all_contracts():
        sondajes = Sondaje.objects.all()
        maquinas = Maquina.objects.all()
        trabajadores = Trabajador.objects.all()
    else:
        sondajes = Sondaje.objects.filter(contrato=contract)
        maquinas = Maquina.objects.filter(contrato=contract)
        trabajadores = Trabajador.objects.filter(contrato=contract)
    
    # Actividades disponibles: utilizamos la relación contrato.actividades
    # (mapeada a la tabla legacy `contratos_actividades`) cuando el usuario
    # está limitado a un contrato. Los administradores de sistema ven todas
    # las actividades por defecto.
    if request.user.can_manage_all_contracts():
        tipos_actividad_qs = TipoActividad.objects.all()
    else:
        # request.user.contrato puede ser None; manejar ese caso
        tipos_actividad_qs = TipoActividad.objects.none()
        if contract:
            try:
                tipos_actividad_qs = contract.actividades.all()
            except Exception:
                # En caso de que la relación through no esté correctamente
                # configurada en la BD, caer de forma segura a conjunto vacío
                tipos_actividad_qs = TipoActividad.objects.none()

    return {
        'sondajes': sondajes.filter(estado='ACTIVO'),
        'maquinas': maquinas.filter(estado='OPERATIVO'),
        'trabajadores': trabajadores.filter(is_active=True),
        'tipos_turno': TipoTurno.objects.all(),
        'tipos_actividad': tipos_actividad_qs,
        'tipos_complemento': TipoComplemento.objects.all(),
        'tipos_aditivo': TipoAditivo.objects.all(),
        'unidades_medida': UnidadMedida.objects.all(),
        'today': timezone.now().date(),
    }


@login_required
def api_create_actividad(request):
    """API pequeña para crear un TipoActividad desde un modal (POST: {'nombre': '...'}).
    Retorna JSON {'ok': True, 'id': x, 'nombre': '...'} o {'ok': False, 'error': '...'}
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    # Permisos: solo usuarios con contrato pueden crear (ajustar según reglas reales)
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'No autenticado'}, status=403)

    nombre = request.POST.get('nombre') or request.POST.get('name')
    if not nombre or not nombre.strip():
        return JsonResponse({'ok': False, 'error': 'Nombre requerido'}, status=400)

    nombre = nombre.strip()
    try:
        actividad = TipoActividad.objects.create(nombre=nombre)
        # Si el usuario no es admin del sistema y tiene contrato, asignar la actividad al contrato
        try:
            if not request.user.can_manage_all_contracts() and getattr(request.user, 'contrato', None):
                request.user.contrato.actividades.add(actividad)
        except Exception:
            # No bloquear la creación por problemas secundarios en la asignación M2M
            pass
        return JsonResponse({'ok': True, 'id': actividad.id, 'nombre': actividad.nombre})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

@login_required
def listar_turnos(request):
    # Filtrar turnos por permisos del usuario
    if request.user.can_manage_all_contracts():
        base_turnos = Turno.objects.all()
        sondajes_filtro = Sondaje.objects.all()
    else:
        # Use the M2M relation 'sondajes' instead of the old FK
        base_turnos = Turno.objects.filter(sondajes__contrato=request.user.contrato)
        sondajes_filtro = Sondaje.objects.filter(contrato=request.user.contrato)
    
    # Aplicar filtros de búsqueda
    filtros = {
        'sondaje': request.GET.get('sondaje', ''),
        'fecha_desde': request.GET.get('fecha_desde', ''),
        'fecha_hasta': request.GET.get('fecha_hasta', ''),
    }
    
    turnos_query = base_turnos
    
    if filtros['sondaje']:
        # filter by selected sondaje id (M2M)
        turnos_query = turnos_query.filter(sondajes__id=filtros['sondaje'])
    
    if filtros['fecha_desde']:
        turnos_query = turnos_query.filter(fecha__gte=filtros['fecha_desde'])
    
    if filtros['fecha_hasta']:
        turnos_query = turnos_query.filter(fecha__lte=filtros['fecha_hasta'])
    
    # SELECT_RELATED y PREFETCH_RELATED con nombres correctos
    # For M2M relations use prefetch_related; select_related only for FKs
    turnos = turnos_query.select_related(
        'maquina', 'tipo_turno'
    ).prefetch_related(
        'sondajes__contrato',
        'trabajadores_turno__trabajador',
    ).order_by('-fecha', '-id')
    
    # Agregar otros prefetch según los nombres reales de tus modelos
    try:
        # TurnoAvance declara related_name='avance' en el modelo, es OneToOne -> usar select_related
        turnos = turnos.select_related('avance')
        # Anotar avance_metros desde TurnoAvance para evitar errores cuando no exista la relación
        from django.db.models import OuterRef, Subquery, DecimalField
        avance_sq = TurnoAvance.objects.filter(turno=OuterRef('pk')).values('metros_perforados')[:1]
        turnos = turnos.annotate(avance_metros=Subquery(avance_sq, output_field=DecimalField()))
    except Exception:
        # Si el nombre difiere en tu modelo, ignorar y continuar
        pass
    
    # Estadísticas
    total_turnos = turnos.count()
    
    # Metros con nombre correcto del modelo
    metros_total = 0
    try:
        # Ajustar según el nombre real de tu modelo de avance
        from django.db.models import Sum
        metros_result = TurnoAvance.objects.filter(
            turno__in=turnos
        ).aggregate(total=Sum('metros_perforados'))
        metros_total = metros_result['total'] or 0
    except:
        metros_total = 0
    
    # Turnos mes actual
    from django.utils import timezone
    hoy = timezone.now().date()
    turnos_mes = turnos.filter(fecha__month=hoy.month, fecha__year=hoy.year).count()
    
    # Promedio
    promedio_avance = metros_total / total_turnos if total_turnos > 0 else 0
    
    # Paginación
    from django.core.paginator import Paginator
    paginator = Paginator(turnos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'turnos': page_obj,
        'sondajes_filtro': sondajes_filtro.filter(estado='ACTIVO'),
        'filtros': filtros,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
        'total_turnos': total_turnos,
        'metros_total': metros_total,
        'turnos_mes': turnos_mes,
        'promedio_avance': promedio_avance,
    }
    
    return render(request, 'drilling/turno/listar.html', context)


class TurnoDetailView(AdminOrContractFilterMixin, DetailView):
    model = Turno
    template_name = 'drilling/turno/detail.html'
    context_object_name = 'turno'


class TurnoDeleteView(AdminOrContractFilterMixin, DeleteView):
    model = Turno
    template_name = 'drilling/turno/confirm_delete.html'
    success_url = reverse_lazy('listar-turnos')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Turno eliminado exitosamente')
        return super().delete(request, *args, **kwargs)


@login_required
def aprobar_turno(request, pk):
    """Vista para que un admin o supervisor apruebe un turno (marca APROBADO)."""
    # Solo admin del sistema o usuarios con rol SUPERVISOR pueden aprobar
    if not (request.user.is_system_admin or request.user.role == 'SUPERVISOR'):
        messages.error(request, 'No tiene permisos para aprobar turnos')
        return redirect('listar-turnos')

    turno = get_object_or_404(Turno, pk=pk)

    if request.method == 'POST':
        turno.estado = 'APROBADO'
        turno.save(update_fields=['estado'])
        messages.success(request, f'Turno #{turno.id} marcado como APROBADO')
        return redirect('listar-turnos')

    return render(request, 'drilling/turno/confirm_approve.html', {'turno': turno})

# ===============================
# ABASTECIMIENTO VIEWS - COMPLETO
# ===============================

class AbastecimientoListView(AdminOrContractFilterMixin, ListView):
    model = Abastecimiento
    template_name = 'drilling/abastecimiento/list.html'
    context_object_name = 'abastecimientos'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'contrato', 'unidad_medida', 'tipo_complemento', 'tipo_aditivo'
        ).order_by('-fecha', '-created_at')
        
        # Filtros adicionales
        familia = self.request.GET.get('familia')
        if familia:
            queryset = queryset.filter(familia=familia)
            
        contrato_id = self.request.GET.get('contrato')
        if contrato_id and self.request.user.can_manage_all_contracts():
            queryset = queryset.filter(contrato_id=contrato_id)
            
        fecha_desde = self.request.GET.get('fecha_desde')
        if fecha_desde:
            queryset = queryset.filter(fecha__gte=fecha_desde)
            
        fecha_hasta = self.request.GET.get('fecha_hasta')
        if fecha_hasta:
            queryset = queryset.filter(fecha__lte=fecha_hasta)
        
        mes = self.request.GET.get('mes')
        if mes:
            queryset = queryset.filter(mes__icontains=mes)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['familias'] = Abastecimiento.FAMILIA_CHOICES
        context['filtros'] = self.request.GET
        
        # Estadísticas rápidas
        queryset = self.get_queryset()
        context['total_registros'] = queryset.count()
        context['valor_total'] = queryset.aggregate(
            total=models.Sum('total')
        )['total'] or 0
        
        return context

class AbastecimientoCreateView(AdminOrContractFilterMixin, CreateView):
    model = Abastecimiento
    form_class = AbastecimientoForm
    template_name = 'drilling/abastecimiento/form.html'
    success_url = reverse_lazy('abastecimiento-list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filtrar contratos accesibles
        form.fields['contrato'].queryset = self.request.user.get_accessible_contracts()
        
        # Si no es admin, preseleccionar su contrato
        if not self.request.user.can_manage_all_contracts():
            form.fields['contrato'].initial = self.request.user.contrato
        
        return form
    
    def form_valid(self, form):
        messages.success(self.request, 'Abastecimiento creado exitosamente')
        return super().form_valid(form)

class AbastecimientoUpdateView(AdminOrContractFilterMixin, UpdateView):
    model = Abastecimiento
    form_class = AbastecimientoForm
    template_name = 'drilling/abastecimiento/form.html'
    success_url = reverse_lazy('abastecimiento-list')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Solo permitir editar si no tiene consumos asociados
        return queryset.annotate(
            tiene_consumos=models.Exists(
                ConsumoStock.objects.filter(abastecimiento=models.OuterRef('pk'))
            )
        ).filter(tiene_consumos=False)
    
    def form_valid(self, form):
        messages.success(self.request, 'Abastecimiento actualizado exitosamente')
        return super().form_valid(form)

class AbastecimientoDetailView(AdminOrContractFilterMixin, DetailView):
    model = Abastecimiento
    template_name = 'drilling/abastecimiento/detail.html'
    context_object_name = 'abastecimiento'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener consumos relacionados. Use prefetch for turno.sondajes (M2M)
        context['consumos'] = ConsumoStock.objects.filter(
            abastecimiento=self.object
        ).select_related('turno').prefetch_related('turno__sondajes').order_by('-created_at')
        
        # Calcular stock disponible
        total_consumido = context['consumos'].aggregate(
            total=models.Sum('cantidad_consumida')
        )['total'] or 0
        
        context['stock_disponible'] = self.object.cantidad - total_consumido
        context['total_consumido'] = total_consumido
        
        return context

class AbastecimientoDeleteView(AdminOrContractFilterMixin, DeleteView):
    model = Abastecimiento
    template_name = 'drilling/abastecimiento/confirm_delete.html'
    success_url = reverse_lazy('abastecimiento-list')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Solo permitir eliminar si no tiene consumos
        return queryset.annotate(
            tiene_consumos=models.Exists(
                ConsumoStock.objects.filter(abastecimiento=models.OuterRef('pk'))
            )
        ).filter(tiene_consumos=False)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Abastecimiento eliminado exitosamente')
        return super().delete(request, *args, **kwargs)

@login_required
def importar_abastecimiento_excel(request):
    """Vista para importar con borrado previo por mes operativo"""
    
    if request.method == 'POST':
        if 'excel_file' not in request.FILES:
            messages.error(request, 'Debe seleccionar un archivo Excel')
            return redirect('importar-abastecimiento')
        
        excel_file = request.FILES['excel_file']
        delete_existing = request.POST.get('delete_existing', 'on') == 'on'
        
        # Validar extensión
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, 'El archivo debe ser formato Excel (.xlsx o .xls)')
            return redirect('importar-abastecimiento')
        
        # Procesar archivo
        importer = AbastecimientoExcelImporter(request.user)
        result = importer.process_excel(excel_file, delete_existing)
        
        if result['success']:
            mensaje_principal = f"Importación completada: {result['success_count']} registros creados"
            
            if result['deleted_count'] > 0:
                mensaje_principal += f", {result['deleted_count']} registros anteriores eliminados"
                
            if result['skip_count'] > 0:
                mensaje_principal += f", {result['skip_count']} registros omitidos"
            
            messages.success(request, mensaje_principal)
            
            # Mostrar información adicional
            if result['meses_procesados']:
                messages.info(
                    request,
                    f"Meses procesados: {', '.join(result['meses_procesados'])}"
                )
            
            if result['contratos_procesados']:
                messages.info(
                    request,
                    f"Contratos afectados: {', '.join(result['contratos_procesados'])}"
                )
            
            # Mostrar errores si los hay
            if result['errors']:
                for error in result['errors'][:10]:  # Mostrar máximo 10 errores
                    messages.warning(request, error)
                    
                if len(result['errors']) > 10:
                    messages.warning(
                        request,
                        f"... y {len(result['errors']) - 10} errores más"
                    )
        else:
            messages.error(request, f"Error en importación: {result['error']}")
            
        return redirect('abastecimiento-list')
    
    # GET - Mostrar formulario de importación
    context = {
        'is_system_admin': request.user.can_manage_all_contracts(),
        'accessible_contracts': request.user.get_accessible_contracts()
    }
    
    return render(request, 'drilling/abastecimiento/importar.html', context)

# ===============================
# CONSUMO STOCK VIEWS - COMPLETO
# ===============================

class ConsumoStockListView(AdminOrContractFilterMixin, ListView):
    model = ConsumoStock
    template_name = 'drilling/consumo/list.html'
    context_object_name = 'consumos'
    paginate_by = 50
    
    def get_queryset(self):
        # Adjust for Turno.sondajes (M2M). Keep select_related for FK fields.
        queryset = ConsumoStock.objects.select_related(
            'turno', 'abastecimiento', 'abastecimiento__unidad_medida'
        ).prefetch_related('turno__sondajes__contrato').order_by('-created_at')
        
        # Filtrar por contrato si no es admin
        if not self.request.user.can_manage_all_contracts():
            queryset = queryset.filter(turno__sondajes__contrato=self.request.user.contrato)
        
        # Filtros adicionales
        contrato_id = self.request.GET.get('contrato')
        if contrato_id and self.request.user.can_manage_all_contracts():
            queryset = queryset.filter(turno__sondajes__contrato_id=contrato_id)
            
        sondaje_id = self.request.GET.get('sondaje')
        if sondaje_id:
            queryset = queryset.filter(turno__sondajes__id=sondaje_id)
            
        fecha_desde = self.request.GET.get('fecha_desde')
        if fecha_desde:
            queryset = queryset.filter(turno__fecha__gte=fecha_desde)
            
        fecha_hasta = self.request.GET.get('fecha_hasta')
        if fecha_hasta:
            queryset = queryset.filter(turno__fecha__lte=fecha_hasta)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtros'] = self.request.GET
        
        # Sondajes disponibles para filtro
        if self.request.user.can_manage_all_contracts():
            context['sondajes'] = Sondaje.objects.all().order_by('nombre_sondaje')
        else:
            context['sondajes'] = Sondaje.objects.filter(
                contrato=self.request.user.contrato
            ).order_by('nombre_sondaje')
        
        return context

class ConsumoStockCreateView(AdminOrContractFilterMixin, CreateView):
    model = ConsumoStock
    form_class = ConsumoStockForm
    template_name = 'drilling/consumo/form.html'
    success_url = reverse_lazy('consumo-list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Filtrar turnos por contrato (use sondajes M2M)
        accessible_contracts = self.request.user.get_accessible_contracts()
        form.fields['turno'].queryset = Turno.objects.filter(
            sondajes__contrato__in=accessible_contracts
        ).prefetch_related('sondajes').order_by('-fecha')
        
        # Filtrar abastecimientos con stock disponible
        form.fields['abastecimiento'].queryset = Abastecimiento.objects.filter(
            contrato__in=accessible_contracts
        ).annotate(
            stock_disponible=models.F('cantidad') - models.Subquery(
                ConsumoStock.objects.filter(
                    abastecimiento=models.OuterRef('pk')
                ).aggregate(
                    total_consumido=models.Sum('cantidad_consumida')
                )['total_consumido'] or 0
            )
        ).filter(stock_disponible__gt=0).order_by('descripcion')
        
        return form
    
    def form_valid(self, form):
        # Validar que hay stock suficiente
        abastecimiento = form.instance.abastecimiento
        cantidad_solicitada = form.instance.cantidad_consumida
        
        stock_actual = abastecimiento.cantidad - (
            ConsumoStock.objects.filter(
                abastecimiento=abastecimiento
            ).aggregate(
                total=models.Sum('cantidad_consumida')
            )['total'] or 0
        )
        
        if cantidad_solicitada > stock_actual:
            form.add_error(
                'cantidad_consumida',
                f'Stock insuficiente. Disponible: {stock_actual}'
            )
            return self.form_invalid(form)
        
        messages.success(self.request, 'Consumo registrado exitosamente')
        return super().form_valid(form)

class ConsumoStockUpdateView(AdminOrContractFilterMixin, UpdateView):
    model = ConsumoStock
    form_class = ConsumoStockForm
    template_name = 'drilling/consumo/form.html'
    success_url = reverse_lazy('consumo-list')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por contrato si no es admin
        if not self.request.user.can_manage_all_contracts():
            queryset = queryset.filter(turno__sondajes__contrato=self.request.user.contrato)
        
        return queryset
    
    def form_valid(self, form):
        messages.success(self.request, 'Consumo actualizado exitosamente')
        return super().form_valid(form)

class ConsumoStockDeleteView(AdminOrContractFilterMixin, DeleteView):
    model = ConsumoStock
    template_name = 'drilling/consumo/confirm_delete.html'
    success_url = reverse_lazy('consumo-list')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por contrato si no es admin
        if not self.request.user.can_manage_all_contracts():
            queryset = queryset.filter(turno__sondajes__contrato=self.request.user.contrato)
        
        return queryset
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Consumo eliminado exitosamente')
        return super().delete(request, *args, **kwargs)

# ===============================
# STOCK DISPONIBLE VIEW
# ===============================

class StockDisponibleView(AdminOrContractFilterMixin, TemplateView):
    template_name = 'drilling/stock/disponible.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calcular stock disponible por producto
        stock_query = '''
            SELECT 
                a.id,
                a.descripcion,
                a.familia,
                a.serie,
                um.simbolo as unidad,
                SUM(a.cantidad) as abastecido,
                COALESCE(SUM(c.cantidad_consumida), 0) as consumido,
                SUM(a.cantidad) - COALESCE(SUM(c.cantidad_consumida), 0) as disponible,
                a.precio_unitario,
                (SUM(a.cantidad) - COALESCE(SUM(c.cantidad_consumida), 0)) * a.precio_unitario as valor_stock
            FROM abastecimiento a
            LEFT JOIN consumo_stock c ON a.id = c.abastecimiento_id
            LEFT JOIN unidades_medida um ON a.unidad_medida_id = um.id
            WHERE a.contrato_id = %s
            GROUP BY a.id, a.descripcion, a.familia, a.serie, um.simbolo, a.precio_unitario
            HAVING SUM(a.cantidad) - COALESCE(SUM(c.cantidad_consumida), 0) > 0
            ORDER BY a.familia, a.descripcion
        '''
        
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(stock_query, [self.request.user.contrato.id])
            stock_data = cursor.fetchall()
        
        # Organizar por familia
        stock_por_familia = {}
        total_valor = 0
        
        for row in stock_data:
            familia = row[2]
            if familia not in stock_por_familia:
                stock_por_familia[familia] = []
            
            stock_por_familia[familia].append({
                'id': row[0],
                'descripcion': row[1],
                'serie': row[3],
                'unidad': row[4],
                'abastecido': row[5],
                'consumido': row[6],
                'disponible': row[7],
                'precio_unitario': row[8],
                'valor_stock': row[9] or 0
            })
            
            total_valor += row[9] or 0
        
        context['stock_por_familia'] = stock_por_familia
        context['total_valor_stock'] = total_valor
        
        return context

# ===============================
# API VIEWS
# ===============================

@login_required
def api_abastecimiento_detalle(request, pk):
    """API para obtener detalles de un abastecimiento"""
    try:
        abastecimiento = get_object_or_404(
            Abastecimiento.objects.filter(contrato=request.user.contrato),
            pk=pk
        )
        
        # Calcular stock disponible
        total_consumido = ConsumoStock.objects.filter(
            abastecimiento=abastecimiento
        ).aggregate(
            total=models.Sum('cantidad_consumida')
        )['total'] or 0
        
        stock_disponible = abastecimiento.cantidad - total_consumido
        
        data = {
            'id': abastecimiento.id,
            'descripcion': abastecimiento.descripcion,
            'serie': abastecimiento.serie,
            'familia': abastecimiento.familia,
            'familia_display': abastecimiento.get_familia_display(),
            'cantidad': str(abastecimiento.cantidad),
            'unidad_medida': abastecimiento.unidad_medida.simbolo,
            'precio_unitario': str(abastecimiento.precio_unitario),
            'total': str(abastecimiento.total),
            'stock_disponible': str(stock_disponible),
            'observaciones': abastecimiento.observaciones,
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)