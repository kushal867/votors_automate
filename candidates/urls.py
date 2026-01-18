from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_view, name='home'),
    path('chat/', views.chat_view, name='chat'),
    path('candidates/', views.CandidateListView.as_view(), name='candidate-list'),
    path('candidate/<int:pk>/', views.CandidateDetailView.as_view(), name='candidate-detail'),
    path('candidate/add/', views.CandidateCreateView.as_view(), name='candidate-add'),
    path('candidate/<int:candidate_id>/upload-manifesto/', views.upload_manifesto, name='upload-manifesto'),
    path('compare/', views.compare_candidates, name='compare-candidates'),
    path('analysis-lab/', views.analysis_lab, name='analysis-lab'),
]
