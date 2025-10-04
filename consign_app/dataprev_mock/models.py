import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.postgres.indexes import GinIndex

def validate_pendencias(value):
    if not isinstance(value, list):
        raise ValidationError("pendencias deve ser uma lista")
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValidationError(f"pendencias[{i}] deve ser objeto")
        if "codigo" not in item or "descricao" not in item:
            raise ValidationError(f"pendencias[{i}] precisa de 'codigo' e 'descricao'")
        if not isinstance(item["codigo"], str) or not isinstance(item["descricao"], str):
            raise ValidationError(f"pendencias[{i}].codigo/descricao devem ser strings")
        if "sigla" in item and item["sigla"] is not None and not isinstance(item["sigla"], str):
            raise ValidationError(f"pendencias[{i}].sigla deve ser string")

class MockINSSEspecie(models.Model):
    codigo = models.CharField(primary_key=True, max_length=10)
    descricao = models.CharField(max_length=120)

class MockINSSSituacao(models.Model):
    codigo = models.CharField(primary_key=True, max_length=10)
    descricao = models.CharField(max_length=120)

class MockINSSBeneficio(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cpf = models.CharField(max_length=11, db_index=True)
    numero_beneficio = models.CharField(max_length=30, unique=True)
    especie = models.ForeignKey(MockINSSEspecie, on_delete=models.PROTECT, db_column="codigo_especie")
    situacao = models.ForeignKey(MockINSSSituacao, on_delete=models.PROTECT, db_column="codigo_situacao")
    data_inicio = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class MockCLTTipoInscricao(models.Model):
    codigo = models.CharField(primary_key=True, max_length=10)
    descricao = models.CharField(max_length=120)

class MockCLTCbo(models.Model):
    codigo = models.CharField(primary_key=True, max_length=10)
    descricao = models.CharField(max_length=120)

class MockCLTRelacao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cpf = models.CharField(max_length=11, db_index=True)

    tipo_inscricao = models.ForeignKey(
        MockCLTTipoInscricao, on_delete=models.PROTECT, db_column="tipo_inscricao"
    )
    numero_inscricao = models.CharField(max_length=14, db_index=True)

    data_admissao = models.DateField()
    data_encerramento = models.DateField(null=True, blank=True)

    cbo = models.ForeignKey(MockCLTCbo, on_delete=models.PROTECT, db_column="cbo_codigo")

    competencia = models.CharField(max_length=7)  # 'YYYY-MM'

    pendencias = models.JSONField(default=list, blank=True, validators=[validate_pendencias])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [GinIndex(fields=["pendencias"])] 