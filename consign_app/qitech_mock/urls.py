# qitech_mock/urls.py
from django.urls import path
from . import views

app_name = "qitech_mock"

urlpatterns = [
    # CaaS – Onboarding PF
    path("onboarding/natural_person", views.onboarding_natural_person, name="onboarding_natural_person"),

    # Documents
    path("upload", views.documents_upload, name="documents_upload"),
    path("document/<uuid:document_key>/url", views.document_url, name="document_url"),

    # LaaS – Debts
    path("debt_simulation", views.debt_simulation, name="debt_simulation"),
    path("debt", views.debt, name="debt"),  # POST issue / GET search
    path("webhooks/dividas", views.debt_webhook, name="debt_webhook"),  # sink (204)

    # BaaS – Account opening PF
    path("account_request/checking", views.account_request_checking, name="account_request_checking"),
    path("account_request/<uuid:account_request_key>/checking",
         views.account_request_checking_patch, name="account_request_checking_patch"),

    # BaaS – Pix
    path("account/<uuid:account_key>/pix_transfer", views.pix_transfer, name="pix_transfer"),
    path("baas/pix/webhooks", views.pix_webhook, name="pix_webhook"),  # sink (204)

    # (Optional) reconciliation-like mock (not required by you, skip if undesired)
    path("baas/account/<uuid:account_key>/transactions", views.account_transactions, name="account_transactions"),
]
