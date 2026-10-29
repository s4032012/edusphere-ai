"""Probe endpoints. /healthz is process liveness; /readyz checks the database only.
Migrations and data-integrity readiness must be verified in the deployment gate.
"""
from django.db import connections
from django.http import JsonResponse
from django.views.decorators.http import require_safe
from django.views.decorators.cache import never_cache

@never_cache
@require_safe
def healthz(request):
    return JsonResponse({'status': 'ok', 'service': 'edusphere-api'})

@never_cache
@require_safe
def readyz(request):
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        # Never expose connection strings, DB usernames or raw exception details.
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ready', 'database': 'connected'})
