from django.urls import path
from . import views

app_name = 'frontend'

urlpatterns = [
    # Frontend root paths
    path('', views.home, name='home'),
    path('register/', views.register_choice, name='register_choice'),
    path('register/borrower/', views.register, name='register'),
    path('register/investor/', views.register_investor, name='register_investor'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('loan-simulation/', views.loan_simulation, name='loan_simulation'),
    path('document-verification/', views.document_verification,
         name='document_verification'),
    path('document-verification/<str:source>/', views.document_verification,
         name='document_verification_with_source'),
    # Lightweight frontend API endpoints (used by frontend JS)
    path('api/offers/<str:offer_id>/register/', views.api_register_offer,
         name='api_register_offer'),
    path('loan-proposal/', views.loan_proposal, name='loan_proposal'),
    path('marketplace/', views.marketplace, name='marketplace'),
    path('marketplace/offer/<str:offer_id>/',
         views.offer_details, name='offer_details'),
    path('welcome/', views.welcome, name='welcome'),
    path('debug/csrf/', views.csrf_debug, name='csrf_debug'),
]
