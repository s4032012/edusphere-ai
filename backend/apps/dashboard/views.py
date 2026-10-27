"""Sprint 6: least-privilege Parent/Student dashboard and local AI preview."""
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from apps.access.views import TenantAPIView
from apps.access.scopes import visible_students
from apps.academics.models import StudentAccount, GuardianLink
from django.db.models import Q
from django.utils import timezone
from .rules import can_open_dashboard
from .services import build_student_dashboard, build_ai_preview


from rest_framework.throttling import UserRateThrottle
from django.utils.cache import patch_vary_headers

class DashboardThrottle(UserRateThrottle):
    rate='60/min'
    def get_cache_key(self,request,view):
        return f"dashboard:{request.user.pk}:{request.headers.get('X-Tenant-ID','')}"

class DashboardBase(TenantAPIView):
    throttle_classes=[DashboardThrottle]
    def finalize_response(self,request,response,*args,**kwargs):
        response=super().finalize_response(request,response,*args,**kwargs)
        response['Cache-Control']='private, no-store'
        patch_vary_headers(response,['Authorization','X-Tenant-ID'])
        return response

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not can_open_dashboard(self.roles):
            raise PermissionDenied('Dashboard chỉ dành cho phụ huynh và học sinh.')
        self.roles &= {'PARENT','STUDENT'}

    def authorized_students(self):
        """Stricter than general visible_students: a parent or a student can view only own links.

        An account holding a separate admin role must not widen access in a consumer app.
        """
        today = timezone.localdate()
        students = visible_students(request_user := self.request.user, self.tenant,
                                    {'PARENT', 'STUDENT'} & self.roles)
        q = Q(pk__in=[])
        if 'PARENT' in self.roles:
            guardians = GuardianLink.objects.filter(tenant=self.tenant, guardian=request_user,
                is_active=True, is_verified=True, can_view_academic=True, valid_from__lte=today).filter(
                Q(valid_to__isnull=True) | Q(valid_to__gte=today)).values('student_id')
            q |= Q(pk__in=guardians)
        if 'STUDENT' in self.roles:
            self_ids = StudentAccount.objects.filter(tenant=self.tenant, account=request_user).values('student_id')
            q |= Q(pk__in=self_ids)
        return students.filter(q)


class DashboardChildren(DashboardBase):
    def get(self, request):
        students = self.authorized_students().order_by('student_code')[:30]
        return Response({'students': [{'id': str(s.id), 'full_name': s.full_name,
                                        'student_code': s.student_code} for s in students]})


class StudentDashboard(DashboardBase):
    def get(self, request, student_id):
        student = get_object_or_404(self.authorized_students(), pk=student_id)
        return Response(build_student_dashboard(view=self, student=student))


class StudentAiPreview(DashboardBase):
    def get(self, request, student_id):
        student = get_object_or_404(self.authorized_students(), pk=student_id)
        snapshot = build_student_dashboard(view=self, student=student)
        return Response({'student_id': str(student.id), 'as_of': snapshot['as_of'],
                         **build_ai_preview(snapshot)})
