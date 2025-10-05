# qitech_mock/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # CaaS – Onboarding PF
    path("onboarding/natural_person", views.onboarding_natural_person),

    # Documents
    path("upload", views.documents_upload),
    path("document/<uuid:document_key>/url", views.document_url),

    # LaaS – Debts
    path("debt_simulation", views.debt_simulation),
    path("debt", views.debt),  # POST issue / GET search
    path("webhooks/dividas", views.debt_webhook),  # sink (204)

    # BaaS – Account opening PF
    path("account_request/checking", views.account_request_checking),
    path("account_request/<uuid:account_request_key>/checking", views.account_request_checking_patch),

    # BaaS – Pix
    path("account/<uuid:account_key>/pix_transfer", views.pix_transfer),
    path("baas/pix/webhooks", views.pix_webhook),  # sink (204)

    # (Optional) reconciliation-like mock (not required by you, skip if undesired)
    path("baas/account/<uuid:account_key>/transactions", views.account_transactions),
]
