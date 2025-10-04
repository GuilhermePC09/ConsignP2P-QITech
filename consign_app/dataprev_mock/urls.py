from django.urls import path
from . import views, auth

urlpatterns = [
    # OAuth “fake” para obter token
    path("oauth/token", views.token_view, name="mock_oauth_token"),

    # Benefícios Previdenciários
    path("beneficios-previdenciarios/v1/beneficios", auth.require_bearer(views.get_beneficios),
         name="mock_beneficios"),

    # Relação Trabalhista (CNIS)
    path("relacao-trabalhista/v1/relacoes-trabalhistas", auth.require_bearer(views.get_relacoes_trabalhistas),
         name="mock_relacoes_trabalhistas"),
]
