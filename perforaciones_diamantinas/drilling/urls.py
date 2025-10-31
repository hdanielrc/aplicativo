from django.urls import path
from . import views

urlpatterns = [
    # Autenticación
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Trabajadores CRUD
    path('trabajadores/', views.TrabajadorListView.as_view(), name='trabajador-list'),
    path('trabajadores/nuevo/', views.TrabajadorCreateView.as_view(), name='trabajador-create'),
    path('trabajadores/<int:pk>/editar/', views.TrabajadorUpdateView.as_view(), name='trabajador-update'),
    path('trabajadores/<int:pk>/eliminar/', views.TrabajadorDeleteView.as_view(), name='trabajador-delete'),
    
    # Máquinas CRUD
    path('maquinas/', views.MaquinaListView.as_view(), name='maquina-list'),
    path('maquinas/nueva/', views.MaquinaCreateView.as_view(), name='maquina-create'),
    path('maquinas/<int:pk>/editar/', views.MaquinaUpdateView.as_view(), name='maquina-update'),
    path('maquinas/<int:pk>/eliminar/', views.MaquinaDeleteView.as_view(), name='maquina-delete'),
    
    # Sondajes CRUD
    path('sondajes/', views.SondajeListView.as_view(), name='sondaje-list'),
    path('sondajes/nuevo/', views.SondajeCreateView.as_view(), name='sondaje-create'),
    path('sondajes/<int:pk>/editar/', views.SondajeUpdateView.as_view(), name='sondaje-update'),
    path('sondajes/<int:pk>/eliminar/', views.SondajeDeleteView.as_view(), name='sondaje-delete'),
    
    # Actividades CRUD
    path('actividades/', views.TipoActividadListView.as_view(), name='actividades-list'),
    path('actividades/nueva/', views.TipoActividadCreateView.as_view(), name='actividades-create'),
    path('actividades/<int:pk>/editar/', views.TipoActividadUpdateView.as_view(), name='actividades-update'),
    path('actividades/<int:pk>/eliminar/', views.TipoActividadDeleteView.as_view(), name='actividades-delete'),
    path('contratos/<int:pk>/actividades/', views.ContratoActividadesUpdateView.as_view(), name='contrato-actividades'),
    
    # Tipos de Turno CRUD
    path('tipos-turno/', views.TipoTurnoListView.as_view(), name='tipo-turno-list'),
    path('tipos-turno/nuevo/', views.TipoTurnoCreateView.as_view(), name='tipo-turno-create'),
    path('tipos-turno/<int:pk>/editar/', views.TipoTurnoUpdateView.as_view(), name='tipo-turno-update'),
    path('tipos-turno/<int:pk>/eliminar/', views.TipoTurnoDeleteView.as_view(), name='tipo-turno-delete'),
    
    # Complementos CRUD
    path('complementos/', views.TipoComplementoListView.as_view(), name='complemento-list'),
    path('complementos/nuevo/', views.TipoComplementoCreateView.as_view(), name='complemento-create'),
    path('complementos/<int:pk>/editar/', views.TipoComplementoUpdateView.as_view(), name='complemento-update'),
    path('complementos/<int:pk>/eliminar/', views.TipoComplementoDeleteView.as_view(), name='complemento-delete'),
    
    # Aditivos CRUD
    path('aditivos/', views.TipoAditivoListView.as_view(), name='aditivo-list'),
    path('aditivos/nuevo/', views.TipoAditivoCreateView.as_view(), name='aditivo-create'),
    path('aditivos/<int:pk>/editar/', views.TipoAditivoUpdateView.as_view(), name='aditivo-update'),
    path('aditivos/<int:pk>/eliminar/', views.TipoAditivoDeleteView.as_view(), name='aditivo-delete'),
    
    # Unidades de Medida CRUD
    path('unidades/', views.UnidadMedidaListView.as_view(), name='unidad-list'),
    path('unidades/nueva/', views.UnidadMedidaCreateView.as_view(), name='unidad-create'),
    path('unidades/<int:pk>/editar/', views.UnidadMedidaUpdateView.as_view(), name='unidad-update'),
    path('unidades/<int:pk>/eliminar/', views.UnidadMedidaDeleteView.as_view(), name='unidad-delete'),
    
    # Turnos
    path('turno/nuevo/', views.crear_turno_completo, name='crear-turno-completo'),
    path('turno/<int:pk>/editar_completo/', views.crear_turno_completo, name='editar-turno-completo'),
    path('turnos/', views.listar_turnos, name='listar-turnos'),
    path('turnos/<int:pk>/', views.TurnoDetailView.as_view(), name='turno-detail'),
    # Edit uses the unified crear_turno_completo view (handles create and edit)
    path('turnos/<int:pk>/editar/', views.crear_turno_completo, name='turno-update'),
    path('turnos/<int:pk>/eliminar/', views.TurnoDeleteView.as_view(), name='turno-delete'),
    path('turnos/<int:pk>/aprobar/', views.aprobar_turno, name='turno-approve'),

    # API endpoints
    path('api/actividades/nuevo/', views.api_create_actividad, name='api-actividad-create'),
    
    # Abastecimiento CRUD Completo
    path('abastecimiento/', views.AbastecimientoListView.as_view(), name='abastecimiento-list'),
    path('abastecimiento/nuevo/', views.AbastecimientoCreateView.as_view(), name='abastecimiento-create'),
    path('abastecimiento/<int:pk>/', views.AbastecimientoDetailView.as_view(), name='abastecimiento-detail'),
    path('abastecimiento/<int:pk>/editar/', views.AbastecimientoUpdateView.as_view(), name='abastecimiento-update'),
    path('abastecimiento/<int:pk>/eliminar/', views.AbastecimientoDeleteView.as_view(), name='abastecimiento-delete'),
    path('abastecimiento/importar/', views.importar_abastecimiento_excel, name='importar-abastecimiento'),
    
    # Consumo CRUD Completo
    path('consumo/', views.ConsumoStockListView.as_view(), name='consumo-list'),
    path('consumo/nuevo/', views.ConsumoStockCreateView.as_view(), name='consumo-create'),
    path('consumo/<int:pk>/editar/', views.ConsumoStockUpdateView.as_view(), name='consumo-update'),
    path('consumo/<int:pk>/eliminar/', views.ConsumoStockDeleteView.as_view(), name='consumo-delete'),
    
    # Stock y Reportes
    path('stock/disponible/', views.StockDisponibleView.as_view(), name='stock-disponible'),
    
    # APIs
    path('api/abastecimiento/<int:pk>/', views.api_abastecimiento_detalle, name='api-abastecimiento-detalle'),
]