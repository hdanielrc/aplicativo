from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse

class ContractSecurityMiddleware:
    """Middleware para seguridad por contrato"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Actualizar última actividad del usuario
        if request.user.is_authenticated:
            request.user.last_activity = timezone.now()
            request.user.save(update_fields=['last_activity'])
        
        response = self.get_response(request)
        return response

class LoginRequiredMiddleware:
    """Middleware para requerir login en todas las URLs excepto login"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = [
            reverse('login'),
        ]

    def __call__(self, request):
        if not request.user.is_authenticated and request.path not in self.exempt_urls:
            return redirect('login')
        
        response = self.get_response(request)
        return response