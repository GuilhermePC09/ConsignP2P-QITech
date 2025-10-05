from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.shortcuts import get_object_or_404
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from .permissions import IsOAuth2Authenticated

from consign_app.core_db.models import (
    Investor, Borrower, LoanOffer, Contract, Installment,
    Payment, KycRisk, Wallet
)
from .serializers import (
    InvestorCreateSerializer, InvestorCreatedSerializer,
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
    """Create a new investor"""
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
    """Create simulation and persist as offer"""

    # Verify borrower exists
    borrower = get_object_or_404(Borrower, borrower_id=borrower_id)

    serializer = SimulationCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    amount = data['amount']
    term_months = data['term_months']

    # Mock rate calculation based on borrower risk
    base_rate = Decimal("2.5")  # Base monthly rate
    risk_adjustment = Decimal("0.0")

    if borrower.risk_score:
        if borrower.risk_score < 6.0:
            risk_adjustment = Decimal("0.8")
        elif borrower.risk_score < 7.5:
            risk_adjustment = Decimal("0.3")
        # else: no adjustment for good scores

    rate = base_rate + risk_adjustment

    # Calculate CET and APR
    monthly_rate = rate / 100
    yearly_rate = (1 + monthly_rate) ** 12 - 1
    apr = yearly_rate * 100
    cet = apr + Decimal("5.0")  # Add fees to CET

    # Create the offer
    offer = LoanOffer.objects.create(
        borrower=borrower,
        amount=amount,
        rate=rate,
        term_months=term_months,
        valid_until=date.today() + timedelta(days=30),
        status="draft",
        cet=cet,
        apr=apr,
        fees={
            "origination_fee": float(amount * Decimal("0.02")),
            "iof": float(amount * Decimal("0.0038")),
            "insurance": 150.00
        },
        external_reference=f"SIM-{uuid.uuid4()}"
    )

    # Generate preview installments
    if monthly_rate == 0:
        pmt = amount / term_months
    else:
        pmt = amount * (monthly_rate * (1 + monthly_rate) ** term_months) / \
            ((1 + monthly_rate) ** term_months - 1)

    preview_installments = []
    for i in range(term_months):
        due_date = date.today() + timedelta(days=30 * (i + 1))
        preview_installments.append({
            "due_date": due_date,
            "amount": pmt
        })

    result_data = {
        "offer_id": offer.offer_id,
        "cet": cet,
        "apr": apr,
        "preview_installments": preview_installments,
        "external_reference": offer.external_reference
    }

    serializer = SimulationResultSerializer(result_data)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


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
