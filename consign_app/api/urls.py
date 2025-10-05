from django.urls import path
from . import views

urlpatterns = [
    # Test endpoint
    path('test/', views.test_auth, name='test_auth'),

    # User registration endpoints
    path('auth/register/investor/',
         views.register_investor, name='register_investor'),
    path('auth/register/borrower/',
         views.register_borrower, name='register_borrower'),
    path('auth/profile/', views.user_profile, name='user_profile'),

    # Investor endpoints
    path('investors/', views.investor_create, name='investor_create'),
    path('investors/<str:investor_id>/offers/',
         views.investor_list_offers, name='investor_list_offers'),
    path('offers/<str:offer_id>/', views.investor_get_offer,
         name='investor_get_offer'),
    path('investors/<str:investor_id>/history/',
         views.investor_get_history, name='investor_get_history'),
    path('investors/<str:investor_id>/kyc/',
         views.investor_kyc_status, name='investor_kyc_status'),
    path('investors/<str:investor_id>/kyc/submit/',
         views.investor_kyc_submit, name='investor_kyc_submit'),

    # Borrower endpoints
    path('borrowers/', views.borrower_create, name='borrower_create'),
    path('borrowers/<str:borrower_id>/simulation/',
         views.borrower_create_simulation, name='borrower_create_simulation'),
    path('borrowers/<str:borrower_id>/kyc/',
         views.borrower_kyc_status, name='borrower_kyc_status'),
    path('borrowers/<str:borrower_id>/kyc/submit/',
         views.borrower_kyc_submit, name='borrower_kyc_submit'),
]
