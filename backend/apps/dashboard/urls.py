from django.urls import path
from .views import DashboardChildren,StudentDashboard,StudentAiPreview
urlpatterns=[
    path('children/',DashboardChildren.as_view()),
    path('students/<uuid:student_id>/',StudentDashboard.as_view()),
    path('students/<uuid:student_id>/ai-preview/',StudentAiPreview.as_view()),
]
