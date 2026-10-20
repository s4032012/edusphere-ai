from apps.access.sprint1_views import (YearView, SubjectView, StaffView, StudentUpdateView, StudentArchiveView,
 ClassroomDetailView, EnrollmentListView, EnrollmentEndView, AssignmentListView, AssignmentEndView,
 GuardianListView, GuardianAccountView, AuditListView, SchoolDashboardView)
from django.urls import path
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenObtainPairView
from apps.access.views import MeView, StudentListCreateView, StudentDetailView, ClassroomListCreateView
from apps.access.views import TeacherAssignmentCreateView, GuardianLinkCreateView, EnrollmentCreateView, GuardianVerifyView

urlpatterns = [
    path('api/v1/admin/dashboard/', SchoolDashboardView.as_view()),
    path('api/v1/academic-years/', YearView.as_view()),
    path('api/v1/subjects/', SubjectView.as_view()),
    path('api/v1/staff/', StaffView.as_view()),
    path('api/v1/classrooms/<uuid:classroom_id>/', ClassroomDetailView.as_view()),
    path('api/v1/students/<uuid:student_id>/edit/', StudentUpdateView.as_view()),
    path('api/v1/students/<uuid:student_id>/archive/', StudentArchiveView.as_view()),
    path('api/v1/enrollments/list/', EnrollmentListView.as_view()),
    path('api/v1/enrollments/<uuid:enrollment_id>/end/', EnrollmentEndView.as_view()),
    path('api/v1/teacher-assignments/list/', AssignmentListView.as_view()),
    path('api/v1/teacher-assignments/<uuid:assignment_id>/end/', AssignmentEndView.as_view()),
    path('api/v1/guardian-accounts/', GuardianAccountView.as_view()),
    path('api/v1/guardian-links/list/', GuardianListView.as_view()),
    path('api/v1/audit-events/', AuditListView.as_view()),
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
