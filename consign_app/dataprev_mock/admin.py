from django.contrib import admin
from .models import (
    MockINSSEspecie, MockINSSSituacao, MockINSSBeneficio,
    MockCLTTipoInscricao, MockCLTCbo, MockCLTRelacao
)

@admin.register(MockINSSEspecie)
class EspAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descricao")
    search_fields = ("codigo", "descricao")

@admin.register(MockINSSSituacao)
class SitAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descricao")
    search_fields = ("codigo", "descricao")

@admin.register(MockINSSBeneficio)
class BenAdmin(admin.ModelAdmin):
    list_display = ("numero_beneficio", "cpf", "especie", "situacao", "data_inicio")
    search_fields = ("numero_beneficio", "cpf")
    list_filter = ("especie", "situacao")

@admin.register(MockCLTTipoInscricao)
class TipoInscAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descricao")
    search_fields = ("codigo", "descricao")

@admin.register(MockCLTCbo)
class CboAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descricao")
    search_fields = ("codigo", "descricao")

@admin.register(MockCLTRelacao)
class RelAdmin(admin.ModelAdmin):
    list_display = ("cpf", "tipo_inscricao", "numero_inscricao", "cbo", "competencia", "data_admissao", "data_encerramento")
    search_fields = ("cpf", "numero_inscricao")
    list_filter = ("tipo_inscricao", "cbo", "competencia")
