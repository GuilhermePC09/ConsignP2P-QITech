from rest_framework import serializers
from decimal import Decimal
from datetime import date, timedelta
from consign_app.core_db.models import (
    Investor, Borrower, LoanOffer, Contract, Installment,
    Payment, Disbursement, Payout, KycRisk, Wallet
)


class InvestorCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating investors"""
    class Meta:
        model = Investor
        fields = ['name', 'document', 'email',
                  'phone_number', 'preferred_payout_method']

    def validate_document(self, value):
        # Basic CPF/CNPJ validation
        if len(value) not in [11, 14]:
            raise serializers.ValidationError(
                "Document must be 11 (CPF) or 14 (CNPJ) digits")
        return value

    def create(self, validated_data):
        # Set default values for new investor
        validated_data.update({
            'type': 'pf' if len(validated_data['document']) == 11 else 'pj',
            'kyc_status': 'pending',
            'status': 'active'
        })
        return super().create(validated_data)


class InvestorCreatedSerializer(serializers.ModelSerializer):
    """Response for investor creation"""
    investor_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Investor
        fields = ['investor_id', 'name', 'document', 'email',
                  'phone_number', 'type', 'kyc_status', 'status']


class OfferSummarySerializer(serializers.ModelSerializer):
    """Summary of loan offers for marketplace"""
    offer_id = serializers.UUIDField(read_only=True)
    borrower_risk = serializers.SerializerMethodField()
    issuer = serializers.SerializerMethodField()

    class Meta:
        model = LoanOffer
        fields = [
            'offer_id', 'amount', 'rate', 'term_months', 'cet', 'apr',
            'issuer', 'borrower_risk', 'valid_until', 'status'
        ]

    def get_borrower_risk(self, obj):
        """Get risk classification from borrower's KYC assessment"""
        try:
            kyc = KycRisk.objects.filter(
                subject_type='borrower',
                subject_id=obj.borrower.borrower_id
            ).first()

            if kyc and kyc.score:
                if kyc.score >= 8.0:
                    return "low"
                elif kyc.score >= 6.5:
                    return "medium"
                else:
                    return "high"
        except:
            pass
        return "medium"

    def get_issuer(self, obj):
        return "QI Tech"


class PreviewInstallmentSerializer(serializers.Serializer):
    """Preview installment for simulations"""
    due_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)


class OfferDetailSerializer(OfferSummarySerializer):
    """Detailed offer information"""
    preview_installments = serializers.SerializerMethodField()
    fees = serializers.JSONField(read_only=True)
    borrower_public = serializers.SerializerMethodField()

    class Meta(OfferSummarySerializer.Meta):
        fields = OfferSummarySerializer.Meta.fields + [
            'preview_installments', 'fees', 'borrower_public'
        ]

    def get_preview_installments(self, obj):
        """Generate preview installments"""
        # Simple PRICE calculation
        monthly_rate = obj.rate / 100
        amount = obj.amount
        term = obj.term_months

        if monthly_rate == 0:
            pmt = amount / term
        else:
            pmt = amount * (monthly_rate * (1 + monthly_rate) ** term) / \
                ((1 + monthly_rate) ** term - 1)

        installments = []
        for i in range(term):
            due_date = date.today() + timedelta(days=30 * (i + 1))
            installments.append({
                "due_date": due_date,
                "amount": pmt
            })

        return installments

    def get_borrower_public(self, obj):
        """Public borrower information (anonymized)"""
        try:
            kyc = KycRisk.objects.filter(
                subject_type='borrower',
                subject_id=obj.borrower.borrower_id
            ).first()

            agreement = obj.borrower.consignment_agreement

            return {
                "risk_score": str(kyc.score) if kyc and kyc.score else "N/A",
                "employment_type": "public_servant",  # Consignment implies public servant
                "region": "Southeast",  # Mock region
                "consigned_margin": str(obj.borrower.consigned_margin),
                "issuer": agreement.issuer if agreement else "N/A"
            }
        except:
            return {
                "risk_score": "N/A",
                "employment_type": "public_servant",
                "region": "Southeast",
                "consigned_margin": "N/A",
                "issuer": "N/A"
            }


class ContractSummarySerializer(serializers.ModelSerializer):
    """Contract summary for history"""
    contract_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Contract
        fields = [
            'contract_id', 'ccb_number', 'status', 'principal_amount',
            'rate', 'term_months', 'activated_at', 'closed_at'
        ]


class InstallmentSerializer(serializers.ModelSerializer):
    """Installment information"""
    installment_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Installment
        fields = [
            'installment_id', 'sequence', 'due_date', 'amount_due',
            'status', 'paid_at'
        ]


class PaymentSerializer(serializers.ModelSerializer):
    """Payment information"""
    payment_id = serializers.UUIDField(read_only=True)
    contract_id = serializers.CharField(
        source='contract.contract_id', read_only=True)
    installment_id = serializers.CharField(
        source='installment.installment_id', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'payment_id', 'contract_id', 'installment_id', 'amount',
            'paid_at', 'status', 'end_to_end_id'
        ]


class InvestorHistorySerializer(serializers.Serializer):
    """Consolidated investor history"""
    contracts = ContractSummarySerializer(many=True, read_only=True)
    installments = InstallmentSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)


# Borrower Serializers
class BorrowerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating borrowers"""
    class Meta:
        model = Borrower
        fields = ['name', 'document', 'email', 'phone_number']

    def validate_document(self, value):
        # CPF validation
        if len(value) != 11:
            raise serializers.ValidationError(
                "Document must be 11 digits (CPF)")
        return value

    def create(self, validated_data):
        # Set default values for new borrower
        validated_data.update({
            'kyc_status': 'pending',
            'credit_status': 'pending'
        })
        return super().create(validated_data)


class BorrowerCreatedSerializer(serializers.ModelSerializer):
    """Response for borrower creation"""
    borrower_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Borrower
        fields = ['borrower_id', 'name', 'document', 'email',
                  'phone_number', 'kyc_status', 'credit_status']


class SimulationCreateSerializer(serializers.Serializer):
    """Serializer for simulation creation"""
    amount = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=1000)
    term_months = serializers.IntegerField(min_value=6, max_value=72)
    disbursement_date = serializers.DateField(required=False, allow_null=True)


class SimulationResultSerializer(serializers.Serializer):
    """Serializer for simulation results"""
    offer_id = serializers.UUIDField()
    cet = serializers.DecimalField(max_digits=9, decimal_places=6)
    apr = serializers.DecimalField(max_digits=9, decimal_places=6)
    preview_installments = PreviewInstallmentSerializer(many=True)
    external_reference = serializers.CharField()


# KYC Serializers
class KycStatusSerializer(serializers.Serializer):
    """KYC status response"""
    kyc_status = serializers.CharField()
    reason = serializers.CharField(required=False, allow_null=True)


class KycSubmitSerializer(serializers.Serializer):
    """KYC submission data"""
    name = serializers.CharField(max_length=255)
    tax_id = serializers.CharField(max_length=14)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=32, required=False)
    address = serializers.JSONField(required=False)
    documents = serializers.ListField(
        child=serializers.JSONField(),
        required=False
    )


class KycSubmittedSerializer(serializers.Serializer):
    """KYC submission response"""
    status = serializers.CharField()
    natural_person_key = serializers.CharField(required=False, allow_null=True)
    legal_person_key = serializers.CharField(required=False, allow_null=True)
