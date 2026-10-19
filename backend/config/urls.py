from django.urls import path
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenObtainPairView
from apps.access.views import MeView, StudentListCreateView, StudentDetailView, ClassroomListCreateView
from apps.access.views import TeacherAssignmentCreateView, GuardianLinkCreateView, EnrollmentCreateView, GuardianVerifyView

urlpatterns = [
    path('healthz/', lambda request: JsonResponse({'status': 'ok', 'service': 'edusphere-api'})),
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token'),
    path('api/v1/me/', MeView.as_view(), name='me'),
    path('api/v1/classrooms/', ClassroomListCreateView.as_view(), name='classrooms'),
    path('api/v1/students/', StudentListCreateView.as_view(), name='students'),
    path('api/v1/students/<uuid:student_id>/', StudentDetailView.as_view(), name='student-detail'),
    path('api/v1/enrollments/', EnrollmentCreateView.as_view(), name='enrollments'),
    path('api/v1/guardian-links/<uuid:link_id>/verify/', GuardianVerifyView.as_view(), name='guardian-verify'),
    path('api/v1/teacher-assignments/', TeacherAssignmentCreateView.as_view(), name='teacher-assignments'),
    path('api/v1/guardian-links/', GuardianLinkCreateView.as_view(), name='guardian-links'),
]
