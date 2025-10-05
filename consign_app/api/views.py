from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.shortcuts import get_object_or_404
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
import requests
from django.urls import reverse
from consign_app.api.helper import build_features_for_borrower, analyze_eligibility, FeatureBuildError

from .permissions import IsOAuth2Authenticated

from consign_app.core_db.models import (
    Investor, Borrower, LoanOffer, Contract, Installment,
    Payment, KycRisk, Wallet
)
from .serializers import (
    InvestorCreateSerializer, InvestorCreatedSerializer,
    InvestorStep1Serializer, InvestorStep2Serializer, InvestorStep3Serializer,
    OfferSummarySerializer, OfferDetailSerializer,
    InvestorHistorySerializer, BorrowerCreateSerializer,
    BorrowerCreatedSerializer, SimulationCreateSerializer,
    SimulationResultSerializer, KycStatusSerializer,
    KycSubmitSerializer, KycSubmittedSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'size'
    max_page_size = 200


# ===============================================
# TEST ENDPOINT
# ===============================================

@api_view(['GET'])
@permission_classes([IsOAuth2Authenticated])
def test_auth(request):
    """Test authentication status"""
    try:
        return Response({
            'message': 'OAuth2 authentication working!',
            'authenticated': bool(request.user and request.user.is_authenticated),
            'user': str(request.user) if request.user else 'None',
            'has_auth': bool(request.auth),
            'auth_type': type(request.auth).__name__ if request.auth else 'None',
            'access_granted': True
        })
    except Exception as e:
        return Response({
            'error': f'Exception in test endpoint: {str(e)}',
            'message': 'Test endpoint has errors'
        }, status=500)


# ===============================================
# INVESTOR ENDPOINTS
# ===============================================

@api_view(['POST'])
@permission_classes([IsOAuth2Authenticated])
def investor_create(request):
    """Create a new investor (legacy endpoint - use multi-step instead)"""
    serializer = InvestorCreateSerializer(data=request.data)

    if serializer.is_valid():
        investor = serializer.save()

        # Create primary wallet
        wallet = Wallet.objects.create(
            owner_type="investor",
            owner_id=investor.investor_id,
            currency="BRL",
            available_balance=Decimal("0.00"),
            blocked_balance=Decimal("0.00"),
            status="active",
            external_reference=f"WALLET-INV-{investor.investor_id}",
            account_key=f"ACC-{uuid.uuid4().hex[:12]}"
        )

        investor.primary_wallet = wallet
        investor.save()

        response_data = InvestorCreatedSerializer(investor).data
        return Response(response_data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ===============================================
# MULTI-STEP INVESTOR CREATION ENDPOINTS
# ===============================================

@api_view(['POST'])
@permission_classes([IsOAuth2Authenticated])
def investor_validate_basic_info(request):
    """
    Passo 1: Validar Informações Básicas
    Step 1: Validate Basic Information (name, email, document)
    """
    serializer = InvestorStep1Serializer(data=request.data)

    if serializer.is_valid():
        return Response({
            'message': 'Informações básicas validadas com sucesso',
            'data': serializer.validated_data,
            'next_step': 'contact_preferences'
        }, status=status.HTTP_200_OK)

    return Response({
        'message': 'Erro na validação das informações básicas',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsOAuth2Authenticated])
def investor_validate_contact_preferences(request):
    """
    Passo 2: Validar Contato e Preferências de Investimento
    Step 2: Validate Contact & Investment Preferences
    """
    serializer = InvestorStep2Serializer(data=request.data)

    if serializer.is_valid():
        return Response({
            'message': 'Informações de contato e preferências validadas com sucesso',
            'data': serializer.validated_data,
            'next_step': 'finalize_registration'
        }, status=status.HTTP_200_OK)

    return Response({
        'message': 'Erro na validação das informações de contato',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsOAuth2Authenticated])
def investor_finalize_registration(request):
    """
    Passo 3: Finalizar Cadastro e Criar Investidor
    Step 3: Finalize Registration & Create Investor
    """
    serializer = InvestorStep3Serializer(data=request.data)

    if serializer.is_valid():
        try:
            investor = serializer.save()
            response_data = InvestorCreatedSerializer(investor).data

            return Response({
                'message': 'Investidor criado com sucesso!',
                'investor': response_data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'message': 'Erro ao criar investidor',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        'message': 'Erro na validação final dos dados',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsOAuth2Authenticated])
def investor_registration_process_info(request):
    """
    Informações sobre o processo de cadastro de investidor
    Information about the investor registration process
    """
    return Response({
        'process': {
            'title': 'Cadastro de Investidor',
            'description': 'Processo em 3 passos para cadastrar um novo investidor',
            'steps': [
                {
                    'step': 1,
                    'title': 'Informações Básicas',
                    'description': 'Nome, e-mail e CPF/CNPJ',
                    'endpoint': '/api/investors/validate-basic-info/',
                    'fields': ['name', 'email', 'document']
                },
                {
                    'step': 2,
                    'title': 'Contato e Preferências',
                    'description': 'Telefone, método de pagamento e perfil de investimento',
                    'endpoint': '/api/investors/validate-contact-preferences/',
                    'fields': ['phone_number', 'preferred_payout_method', 'investment_capacity', 'risk_tolerance']
                },
                {
                    'step': 3,
                    'title': 'Finalização do Cadastro',
                    'description': 'Revisar dados e aceitar termos',
                    'endpoint': '/api/investors/finalize-registration/',
                    'fields': ['terms_accepted', 'privacy_accepted']
                }
            ]
        },
        'field_options': {
            'preferred_payout_method': [
                {'value': 'pix', 'label': 'PIX'},
                {'value': 'ted', 'label': 'TED'},
                {'value': 'bank_transfer', 'label': 'Transferência Bancária'}
            ],
            'risk_tolerance': [
                {'value': 'conservative', 'label': 'Conservador'},
                {'value': 'moderate', 'label': 'Moderado'},
                {'value': 'aggressive', 'label': 'Agressivo'}
            ]
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsOAuth2Authenticated])
def investor_list_offers(request, investor_id):
    """List marketplace offers for an investor"""

    # Verify investor exists
    get_object_or_404(Investor, investor_id=investor_id)

    # Start with open offers
    queryset = LoanOffer.objects.filter(status='open')

    # Apply filters
    min_amount = request.GET.get('min_amount')
    max_amount = request.GET.get('max_amount')
    min_rate = request.GET.get('min_rate')
    max_rate = request.GET.get('max_rate')
    min_term = request.GET.get('min_term')
    max_term = request.GET.get('max_term')
    borrower_risk = request.GET.get('borrower_risk')
    issuer = request.GET.get('issuer')
    order_by = request.GET.get('order_by', 'rate')

    if min_amount:
        queryset = queryset.filter(amount__gte=min_amount)
    if max_amount:
        queryset = queryset.filter(amount__lte=max_amount)
    if min_rate:
        queryset = queryset.filter(rate__gte=min_rate)
    if max_rate:
        queryset = queryset.filter(rate__lte=max_rate)
    if min_term:
        queryset = queryset.filter(term_months__gte=min_term)
    if max_term:
        queryset = queryset.filter(term_months__lte=max_term)

    # TODO: Filter by borrower_risk using KycRisk model
    # TODO: Filter by issuer

    # Order results
    order_fields = {
        'rate': 'rate',
        'amount': 'amount',
        'term': 'term_months',
        'cet': 'cet',
        'apr': 'apr'
    }

    if order_by in order_fields:
        queryset = queryset.order_by(order_fields[order_by])

    # Paginate
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)

    serializer = OfferSummarySerializer(page, many=True)

    response = paginator.get_paginated_response(serializer.data)
    response['X-Total-Count'] = queryset.count()

    return response


@api_view(['GET'])
@permission_classes([IsOAuth2Authenticated])
def investor_get_offer(request, offer_id):
    """Get detailed offer information"""

    offer = get_object_or_404(LoanOffer, offer_id=offer_id)
    serializer = OfferDetailSerializer(offer)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsOAuth2Authenticated])
def investor_get_history(request, investor_id):
    """Get investor transaction history"""

    # Verify investor exists
    investor = get_object_or_404(Investor, investor_id=investor_id)

    history_type = request.GET.get('type', 'all')
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')

    # Get contracts where this investor is the creditor
    contracts_qs = Contract.objects.filter(
        creditor_type='investor',
        creditor_id=investor.investor_id
    )

    # Apply date filters
    if from_date:
        contracts_qs = contracts_qs.filter(activated_at__gte=from_date)
    if to_date:
        contracts_qs = contracts_qs.filter(activated_at__lte=to_date)

    history_data = {}

    if history_type in ['all', 'contracts']:
        history_data['contracts'] = contracts_qs

    if history_type in ['all', 'installments']:
        installments_qs = Installment.objects.filter(
            contract__in=contracts_qs
        ).order_by('-due_date')
        history_data['installments'] = installments_qs

    if history_type in ['all', 'payments']:
        payments_qs = Payment.objects.filter(
            contract__in=contracts_qs
        ).order_by('-paid_at')
        history_data['payments'] = payments_qs

    serializer = InvestorHistorySerializer(history_data)
    return Response(serializer.data)


# ===============================================
# BORROWER ENDPOINTS
# ===============================================

@api_view(['POST'])
@permission_classes([IsOAuth2Authenticated])
def borrower_create(request):
    """Create a new borrower"""
    serializer = BorrowerCreateSerializer(data=request.data)

    if serializer.is_valid():
        borrower = serializer.save()
        response_data = BorrowerCreatedSerializer(borrower).data
        return Response(response_data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsOAuth2Authenticated])
def borrower_create_simulation(request, borrower_id):
    borrower = get_object_or_404(Borrower, borrower_id=borrower_id)

    serializer = SimulationCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    amount = data['amount']
    term_months = data['term_months']

    # CPF do borrower (ajuste o campo se necessário)
    cpf = (getattr(borrower, "document", "") or "").replace(".", "").replace("-", "")

    # Overrides opcionais enviados no payload
    overrides = request.data.get('features', {}) or {}

    # ===== monta features via serviços internos (Dataprev/OF) =====
    try:
        features = build_features_for_borrower(
            request=request,
            cpf=cpf,
            amount=float(amount),
            term_months=int(term_months),
            overrides=overrides
        )
    except FeatureBuildError as e:
        return Response({"detail": f"Falha ao montar features: {str(e)}"}, status=400)

    # payload para o /risk/score
    risk_payload = {
        "features": features,
        "amount": float(amount),
        "term_months": int(term_months)
    }

    # Constrói URL absoluta e propaga Authorization
    risk_path = reverse('risk:score')  # path('score', views.score, name='score')
    risk_url = request.build_absolute_uri(risk_path)

    headers = {"Content-Type": "application/json"}
    auth_header = request.META.get("HTTP_AUTHORIZATION")
    if auth_header:
        headers["Authorization"] = auth_header

    # Chama o /risk/score
    try:
        r = requests.post(risk_url, json=risk_payload, headers=headers, timeout=5)
        r.raise_for_status()
        risk = r.json()
    except requests.RequestException as e:
        return Response({"detail": f"Falha ao consultar /risk/score: {e}"},
                        status=status.HTTP_502_BAD_GATEWAY)

    # Usa os campos retornados pelo risk
    monthly_rate = Decimal(str(risk["rate_monthly"]))
    rate = monthly_rate
    apr = Decimal(str(risk.get("rate_yearly_eff", 0)))
    cet = Decimal(str(risk.get("cet_yearly", apr)))

    # Cria a offer
    offer = LoanOffer.objects.create(
        borrower=borrower,
        amount=amount,
        rate=rate,                      # Taxa mensal
        term_months=term_months,
        valid_until=date.today() + timedelta(days=30),
        status="draft",
        cet=cet,                        # CET (a.a.) vindo do risk
        apr=apr,                        # APR (a.a.) vindo do risk
        fees={
            "origination_fee": float(amount * Decimal("0.02")),
            "iof": float(amount * Decimal("0.0038")),
            "insurance": 150.00
        },
        external_reference=f"SIM-{uuid.uuid4()}"
    )

    # Parcela: usa installment do risk se houver; senão calcula localmente
    installment = risk.get("installment")
    if installment is not None:
        pmt = Decimal(str(installment)).quantize(Decimal("0.01"))
    else:
        if monthly_rate == 0:
            pmt = Decimal(amount) / Decimal(term_months)
        else:
            mr = monthly_rate
            n = Decimal(term_months)
            pmt = Decimal(amount) * (mr * (1 + mr) ** n) / ((1 + mr) ** n - 1)
        pmt = pmt.quantize(Decimal("0.01"))

    # Preview de parcelas
    preview_installments = []
    for i in range(term_months):
        due_date = date.today() + timedelta(days=30 * (i + 1))
        preview_installments.append({
            "due_date": due_date,
            "amount": float(pmt)
        })

    # # === Checagem de elegibilidade (band + 35% renda) ===
    try:
        elig = analyze_eligibility(
            band=risk.get("band"),
            # band="C"                                      # ← já vem: "A".."E"
            installment=(Decimal(str(risk["installment"])) if risk.get("installment") is not None else None),
            amount=Decimal(str(amount)) if risk.get("installment") is None else None,
            term_months=int(term_months) if risk.get("installment") is None else None,
            monthly_rate=monthly_rate if risk.get("installment") is None else None,
            features=features,                                      # tem renda_media_6m
            request=request,                                        # fallback p/ buscar renda
            cpf=cpf,
            min_band="D",
            max_income_ratio=Decimal("0.35"),
        )
    except FeatureBuildError as e:
        return Response({"detail": f"Falha na análise de elegibilidade: {str(e)}"}, status=400)

    if not elig["eligible"]:
        return Response({
            "detail": "Empréstimo negado pelas regras de elegibilidade.",
            "reasons": elig["reasons"],           # ["score_insuficiente(<D)"] / ["parcela_acima_35pct_renda"] etc.
            "band": elig["band"],                 # ex.: "C"
            "installment": elig["installment"],   # ex.: 591.63
            "renda_mensal": elig["renda_mensal"], # ex.: 4200.0
            "thresholds": elig["thresholds"],     # min_band, renda_limite_35pct, etc.
        }, status=status.HTTP_400_BAD_REQUEST)

    result_data = {
        "offer_id": offer.offer_id,
        "rate": float(rate),
        "band": risk.get("band"),
        "cet": float(cet),
        "apr": float(apr),
        "preview_installments": preview_installments,
        "external_reference": offer.external_reference
    }

    out = SimulationResultSerializer(result_data)
    return Response(out.data, status=status.HTTP_201_CREATED)

# ===============================================
# KYC ENDPOINTS
# ===============================================

@api_view(['POST'])
@permission_classes([IsOAuth2Authenticated])
def investor_kyc_submit(request, investor_id):
    """Submit investor KYC data"""

    investor = get_object_or_404(Investor, investor_id=investor_id)

    serializer = KycSubmitSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Create or update KYC record
    kyc, created = KycRisk.objects.get_or_create(
        subject_type="investor",
        subject_id=investor.investor_id,
        defaults={
            'provider': 'qi_risk',
            'status': 'in_review',
            'decision_reasons': {'submitted_at': datetime.now().isoformat()},
            'evidences': request.data.get('documents', []),
            'natural_person_key': f"NP-{uuid.uuid4().hex[:12]}",
            'external_reference': f"KYC-INV-{investor.investor_id}"
        }
    )

    # Update investor status
    investor.kyc_status = 'in_review'
    investor.save()

    response_data = {
        'status': 'in_review',
        'natural_person_key': kyc.natural_person_key,
        'legal_person_key': None
    }

    return Response(response_data, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([IsOAuth2Authenticated])
def investor_kyc_status(request, investor_id):
    """Get investor KYC status"""

    investor = get_object_or_404(Investor, investor_id=investor_id)

    response_data = {
        'kyc_status': investor.kyc_status,
        'reason': None
    }

    # Add reason if rejected
    if investor.kyc_status == 'rejected':
        try:
            kyc = KycRisk.objects.get(
                subject_type='investor',
                subject_id=investor.investor_id
            )
            response_data['reason'] = kyc.decision_reasons.get(
                'reason', 'Documents require review')
        except KycRisk.DoesNotExist:
            pass

    return Response(response_data)


@api_view(['POST'])
@permission_classes([IsOAuth2Authenticated])
def borrower_kyc_submit(request, borrower_id):
    """Submit borrower KYC data"""

    borrower = get_object_or_404(Borrower, borrower_id=borrower_id)

    serializer = KycSubmitSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Create or update KYC record
    kyc, created = KycRisk.objects.get_or_create(
        subject_type="borrower",
        subject_id=borrower.borrower_id,
        defaults={
            'provider': 'qi_risk',
            'status': 'in_review',
            'decision_reasons': {'submitted_at': datetime.now().isoformat()},
            'evidences': request.data.get('documents', []),
            'natural_person_key': f"NP-{uuid.uuid4().hex[:12]}",
            'external_reference': f"KYC-BOR-{borrower.borrower_id}"
        }
    )

    # Update borrower status
    borrower.kyc_status = 'in_review'
    borrower.save()

    response_data = {
        'status': 'in_review',
        'natural_person_key': kyc.natural_person_key,
        'legal_person_key': None
    }

    return Response(response_data, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([IsOAuth2Authenticated])
def borrower_kyc_status(request, borrower_id):
    """Get borrower KYC status"""

    borrower = get_object_or_404(Borrower, borrower_id=borrower_id)

    response_data = {
        'kyc_status': borrower.kyc_status,
        'reason': None
    }

    # Add reason if rejected
    if borrower.kyc_status == 'rejected':
        try:
            kyc = KycRisk.objects.get(
                subject_type='borrower',
                subject_id=borrower.borrower_id
            )
            response_data['reason'] = kyc.decision_reasons.get(
                'reason', 'Documents require review')
        except KycRisk.DoesNotExist:
            pass

    return Response(response_data)
