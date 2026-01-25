from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('chat/', views.chat_view, name='chat'),
    path('candidates/', views.CandidateListView.as_view(), name='candidate-list'),
    path('candidate/<int:pk>/', views.CandidateDetailView.as_view(), name='candidate-detail'),
    path('candidate/add/', views.CandidateCreateView.as_view(), name='candidate-add'),
    path('candidate/<int:pk>/edit/', views.CandidateUpdateView.as_view(), name='candidate-edit'),
    path('candidate/<int:pk>/delete/', views.CandidateDeleteView.as_view(), name='candidate-delete'),
    path('candidate/<int:candidate_id>/upload-manifesto/', views.upload_manifesto, name='upload-manifesto'),
    path('compare/', views.compare_candidates, name='compare-candidates'),
    path('search/', views.global_search, name='global-search'),
    path('analysis-lab/', views.analysis_lab, name='analysis-lab'),
    path('candidate/<int:pk>/report/', views.candidate_report_view, name='candidate-report'),
]
