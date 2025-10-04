from django.urls import path
from . import views

urlpatterns = [
    # OAuth (mock)
    path("oauth/token", views.token_view, name="of_oauth_token"),

    # Customers v2
    path("customers/v2/personal/identifications", views.get_customer_identification),

    # Accounts v2
    path("accounts/v2/accounts", views.list_accounts),
    path("accounts/v2/<str:account_id>/balances", views.get_account_balances),
    path("accounts/v2/<str:account_id>/transactions", views.get_account_transactions),

    # Credit Cards v2
    path("credit-cards-accounts/v2/accounts", views.list_cc_accounts),
    path("credit-cards-accounts/v2/<str:account_id>/bills", views.list_cc_bills),
    path("credit-cards-accounts/v2/<str:account_id>/transactions", views.list_cc_transactions),

    # Loans v2
    path("loans/v2/contracts", views.list_loan_contracts),
    path("loans/v2/contracts/<str:contract_id>", views.get_loan_contract),
    path("loans/v2/contracts/<str:contract_id>/payments", views.list_loan_payments),
    path("loans/v2/contracts/<str:contract_id>/installments", views.list_loan_installments),  # útil p/ UI
]
