from django.urls import path
from . import views

app_name = 'frontend'

urlpatterns = [
    # Frontend root paths
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('loan-simulation/', views.loan_simulation, name='loan_simulation'),
    path('document-verification/', views.document_verification,
         name='document_verification'),
    path('document-verification/<str:source>/', views.document_verification,
         name='document_verification_with_source'),
    path('loan-proposal/', views.loan_proposal, name='loan_proposal'),
    path('marketplace/', views.marketplace, name='marketplace'),
    path('welcome/', views.welcome, name='welcome'),
    path('debug/csrf/', views.csrf_debug, name='csrf_debug'),
]
