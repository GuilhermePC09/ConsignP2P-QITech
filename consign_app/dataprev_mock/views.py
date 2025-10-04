from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt 

from .auth import require_bearer
from .models import (
    MockINSSBeneficio, MockINSSEspecie, MockINSSSituacao,
    MockCLTRelacao, MockCLTTipoInscricao, MockCLTCbo
)

# ------------------- helpers -------------------
def _ym_ok(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m")
        return True
    except Exception:
        return False

def _beneficio_dict(b: MockINSSBeneficio) -> Dict[str, Any]:
    return {
        "cpf": b.cpf,
        "numeroBeneficio": b.numero_beneficio,
        "codigoEspecie": b.especie_id,
        "descricaoEspecie": b.especie.descricao if b.especie else None,
        "codigoSituacao": b.situacao_id,
        "descricaoSituacao": b.situacao.descricao if b.situacao else None,
        "dataInicio": b.data_inicio.strftime("%Y-%m-%d"),
    }

def _relacao_dict(r: MockCLTRelacao) -> Dict[str, Any]:
    return {
        "tipoInscricao": r.tipo_inscricao_id,                 # código do tipo
        "numeroInscricao": r.numero_inscricao,                # CNPJ/CPF empregador
        "dataAdmissao": r.data_admissao.strftime("%Y-%m-%d"),
        "dataEncerramento": r.data_encerramento.strftime("%Y-%m-%d") if r.data_encerramento else None,
        "cbo": {"codigo": r.cbo_id, "descricao": r.cbo.descricao if r.cbo else None},
        "remuneracao": {"competencia": r.competencia},        # YYYY-MM
        "pendencias": r.pendencias or [],
    }

# ------------------- OAuth mock -------------------
@require_http_methods(["POST"])
@csrf_exempt
def token_view(request):
    now = datetime.utcnow()
    return JsonResponse({
        "access_token": "mock-access-token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "read",
        "issued_at": int(now.timestamp()),
        "expires_at": int((now + timedelta(seconds=3600)).timestamp()),
    }, status=200)

# ------------------- Benefícios Previdenciários -------------------
@require_http_methods(["GET"])
@require_bearer
def get_beneficios(request):
    cpf = (request.GET.get("cpf") or "").replace(".", "").replace("-", "")
    cod_especie = request.GET.get("codigoEspecie")
    cod_situacao = request.GET.get("codigoSituacao")
    data_inicio_de = request.GET.get("dataInicioDe")   # opcional YYYY-MM-DD
    data_inicio_ate = request.GET.get("dataInicioAte") # opcional YYYY-MM-DD

    if not cpf:
        return JsonResponse({"message": "Parâmetro cpf é obrigatório."}, status=400)

    qs = (MockINSSBeneficio.objects
          .select_related("especie", "situacao")
          .filter(cpf=cpf))

    if cod_especie:
        qs = qs.filter(especie_id=cod_especie)
    if cod_situacao:
        qs = qs.filter(situacao_id=cod_situacao)
    if data_inicio_de:
        qs = qs.filter(data_inicio__gte=data_inicio_de)
    if data_inicio_ate:
        qs = qs.filter(data_inicio__lte=data_inicio_ate)

    data = [_beneficio_dict(b) for b in qs.order_by("-data_inicio")]

    # fallback mínimo para não retornar 200 vazio em ambiente zerado
    if not data:
        data = [{
            "cpf": cpf,
            "numeroBeneficio": "1234567890",
            "codigoEspecie": "32",
            "descricaoEspecie": "APOSENTADORIA POR TEMPO DE CONTRIBUIÇÃO",
            "codigoSituacao": "1",
            "descricaoSituacao": "ATIVO",
            "dataInicio": "2019-05-01",
        }]

    return JsonResponse({"beneficios": data}, status=200, json_dumps_params={"ensure_ascii": False})

# ------------------- Relação Trabalhista (CNIS) -------------------
@require_http_methods(["GET"])
@require_bearer
def get_relacoes_trabalhistas(request):
    cpf = (request.GET.get("cpf") or "").replace(".", "").replace("-", "")
    tipo_inscricao = request.GET.get("tipoInscricao")       # ex: "CNPJ"
    numero_inscricao = request.GET.get("numeroInscricao")   # ex: CNPJ/CPF do empregador
    competencia = request.GET.get("competencia")            # YYYY-MM
    competencia_de = request.GET.get("competenciaDe")       # YYYY-MM
    competencia_ate = request.GET.get("competenciaAte")     # YYYY-MM

    if not cpf:
        return JsonResponse({"message": "Parâmetro cpf é obrigatório."}, status=400)

    qs = (MockCLTRelacao.objects
          .select_related("tipo_inscricao", "cbo")
          .filter(cpf=cpf))

    if tipo_inscricao:
        qs = qs.filter(tipo_inscricao_id=tipo_inscricao)
    if numero_inscricao:
        qs = qs.filter(numero_inscricao=numero_inscricao)
    if competencia and _ym_ok(competencia):
        qs = qs.filter(competencia=competencia)
    else:
        if competencia_de and _ym_ok(competencia_de):
            qs = qs.filter(competencia__gte=competencia_de)
        if competencia_ate and _ym_ok(competencia_ate):
            qs = qs.filter(competencia__lte=competencia_ate)

    data = [_relacao_dict(r) for r in qs.order_by("-competencia", "-data_admissao")]

    if not data:
        data = [{
            "tipoInscricao": "CNPJ",
            "numeroInscricao": "11222333000144",
            "dataAdmissao": "2021-03-10",
            "dataEncerramento": None,
            "cbo": {"codigo": "252505", "descricao": "Analista de sistemas"},
            "remuneracao": {"competencia": "2024-08"},
            "pendencias": [{"codigo": "P00", "sigla": "OK", "descricao": "Sem pendências"}],
        }]

    return JsonResponse({"cpf": cpf, "relacoesTrabalhistas": data},
                        status=200, json_dumps_params={"ensure_ascii": False})
