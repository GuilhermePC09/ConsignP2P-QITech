from rest_framework import serializers
from decimal import Decimal
from datetime import date, timedelta
import uuid
from django.contrib.auth.models import User
from consign_app.core_db.models import (
    Investor, Borrower, LoanOffer, Contract, Installment,
    Payment, Disbursement, Payout, KycRisk, Wallet
)


def validate_cpf(cpf):
    """
    Validate Brazilian CPF (Cadastro de Pessoas Físicas)
    Returns True if valid, False otherwise
    """
    # Remove formatting
    cpf = ''.join(filter(str.isdigit, cpf))

    # Check if it has 11 digits
    if len(cpf) != 11:
        return False

    # Check if all digits are the same (invalid CPFs like 111.111.111-11)
    if cpf == cpf[0] * 11:
        return False

    # Calculate first verification digit
    sum1 = 0
    for i in range(9):
        sum1 += int(cpf[i]) * (10 - i)

    remainder1 = sum1 % 11
    digit1 = 0 if remainder1 < 2 else 11 - remainder1

    if int(cpf[9]) != digit1:
        return False

    # Calculate second verification digit
    sum2 = 0
    for i in range(10):
        sum2 += int(cpf[i]) * (11 - i)

    remainder2 = sum2 % 11
    digit2 = 0 if remainder2 < 2 else 11 - remainder2

    if int(cpf[10]) != digit2:
        return False

    return True


# ===============================================
# USER AUTHENTICATION SERIALIZERS
# ===============================================

class UserRegistrationSerializer(serializers.Serializer):
    """Base serializer for user registration"""
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    first_name = serializers.CharField(max_length=30, required=False)
    last_name = serializers.CharField(max_length=150, required=False)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value


class InvestorUserRegistrationSerializer(UserRegistrationSerializer):
    """Serializer for registering a new investor user"""
    # Investor-specific fields
    name = serializers.CharField(max_length=255)
    document = serializers.CharField(max_length=32)
    phone_number = serializers.CharField(max_length=32, required=False)
    preferred_payout_method = serializers.CharField(
        max_length=16, required=False)

    def validate_document(self, value):
        # Basic CPF/CNPJ validation
        if len(value) not in [11, 14]:
            raise serializers.ValidationError(
                "Document must be 11 (CPF) or 14 (CNPJ) digits")

        # Check if document already exists
        if Investor.objects.filter(document=value).exists():
            raise serializers.ValidationError("Document already registered")

        return value

    def create(self, validated_data):
        # Extract user fields
        user_fields = ['username', 'email',
                       'password', 'first_name', 'last_name']
        user_data = {k: validated_data.pop(
            k) for k in user_fields if k in validated_data}
        password = user_data.pop('password')

        # Create user
        user = User.objects.create_user(**user_data, password=password)

        # Create investor
        investor_data = validated_data.copy()
        investor_data.update({
            'user': user,
            'type': 'pf' if len(investor_data['document']) == 11 else 'pj',
            'kyc_status': 'pending',
            'status': 'active',
            'email': user.email,  # sync with user email
        })

        investor = Investor.objects.create(**investor_data)

        # Create primary wallet
        from decimal import Decimal
        import uuid
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

        return investor


class BorrowerUserRegistrationSerializer(UserRegistrationSerializer):
    """Serializer for registering a new borrower user"""
    # Borrower-specific fields
    name = serializers.CharField(max_length=255)
    document = serializers.CharField(max_length=32)
    phone_number = serializers.CharField(max_length=32, required=False)

    def validate_document(self, value):
        # Clean the CPF by removing formatting characters
        clean_cpf = ''.join(filter(str.isdigit, value))

        # Validate CPF using the proper algorithm
        if not validate_cpf(clean_cpf):
            raise serializers.ValidationError(
                "CPF inválido. Verifique os dígitos informados")

        # Check if document already exists
        if Borrower.objects.filter(document=clean_cpf).exists():
            raise serializers.ValidationError("CPF já está cadastrado")

        # Return the clean CPF without formatting
        return clean_cpf

    def create(self, validated_data):
        # Extract user fields
        user_fields = ['username', 'email',
                       'password', 'first_name', 'last_name']
        user_data = {k: validated_data.pop(
            k) for k in user_fields if k in validated_data}
        password = user_data.pop('password')

        # Create user
        user = User.objects.create_user(**user_data, password=password)

        # Create borrower
        borrower_data = validated_data.copy()
        borrower_data.update({
            'user': user,
            'kyc_status': 'pending',
            'credit_status': 'pending',
            'email': user.email,  # sync with user email
        })

        borrower = Borrower.objects.create(**borrower_data)

        return borrower


# ===============================================
# EXISTING SERIALIZERS
# ===============================================


class InvestorCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating investors"""
    class Meta:
        model = Investor
        fields = ['name', 'document', 'email',
                  'phone_number', 'preferred_payout_method']

    def validate_document(self, value):
        # Remove formatting characters
        clean_doc = ''.join(filter(str.isdigit, value))

        # Validate based on length (CPF or CNPJ)
        if len(clean_doc) == 11:
            # CPF validation
            if not validate_cpf(clean_doc):
                raise serializers.ValidationError(
                    "CPF inválido. Verifique os dígitos informados")
        elif len(clean_doc) == 14:
            # CNPJ validation (for now just check length)
            pass  # TODO: Add proper CNPJ validation
        else:
            raise serializers.ValidationError(
                "CPF deve ter 11 dígitos ou CNPJ deve ter 14 dígitos")

        return clean_doc

    def create(self, validated_data):
        # Set default values for new investor
        validated_data.update({
            'type': 'pf' if len(validated_data['document']) == 11 else 'pj',
            'kyc_status': 'pending',
            'status': 'active'
        })
        return super().create(validated_data)


# ===============================================
# MULTI-STEP INVESTOR CREATION SERIALIZERS
# ===============================================

class InvestorStep1Serializer(serializers.Serializer):
    """Step 1: Informações Básicas - Basic Information"""
    name = serializers.CharField(max_length=255, help_text="Nome completo")
    email = serializers.EmailField(help_text="E-mail para acesso")
    document = serializers.CharField(max_length=14, help_text="CPF ou CNPJ")

    def validate_document(self, value):
        # Remove formatting characters
        clean_doc = ''.join(filter(str.isdigit, value))

        # Validate based on length (CPF or CNPJ)
        if len(clean_doc) == 11:
            # CPF validation
            if not validate_cpf(clean_doc):
                raise serializers.ValidationError(
                    "CPF inválido. Verifique os dígitos informados")
        elif len(clean_doc) == 14:
            # CNPJ validation (for now just check length, can add CNPJ algorithm later)
            pass  # TODO: Add proper CNPJ validation
        else:
            raise serializers.ValidationError(
                "CPF deve ter 11 dígitos ou CNPJ deve ter 14 dígitos")

        # Check if document already exists
        if Investor.objects.filter(document=clean_doc).exists():
            raise serializers.ValidationError(
                "CPF/CNPJ já está cadastrado")

        return clean_doc

    def validate_email(self, value):
        # Check if email already exists
        if Investor.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "E-mail já está cadastrado")
        return value


class InvestorStep2Serializer(serializers.Serializer):
    """Step 2: Contato e Preferências - Contact & Investment Preferences"""
    phone_number = serializers.CharField(
        max_length=20, help_text="Telefone com DDD")
    preferred_payout_method = serializers.ChoiceField(
        choices=[('pix', 'PIX'), ('ted', 'TED'),
                 ('bank_transfer', 'Transferência Bancária')],
        default='pix',
        help_text="Método preferido para recebimento"
    )
    investment_capacity = serializers.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Capacidade de investimento mensal (R$)"
    )
    risk_tolerance = serializers.ChoiceField(
        choices=[('conservative', 'Conservador'), ('moderate',
                                                   'Moderado'), ('aggressive', 'Agressivo')],
        default='moderate',
        help_text="Perfil de risco"
    )

    def validate_phone_number(self, value):
        # Remove formatting characters
        clean_phone = ''.join(filter(str.isdigit, value))

        if len(clean_phone) < 10 or len(clean_phone) > 11:
            raise serializers.ValidationError(
                "Telefone deve ter 10 ou 11 dígitos")

        return value


class InvestorStep3Serializer(serializers.Serializer):
    """Step 3: Revisão e Confirmação - Review & Confirmation"""
    # All data from previous steps
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    document = serializers.CharField(max_length=14)
    phone_number = serializers.CharField(max_length=20)
    preferred_payout_method = serializers.ChoiceField(
        choices=[('pix', 'PIX'), ('ted', 'TED'),
                 ('bank_transfer', 'Transferência Bancária')]
    )
    investment_capacity = serializers.DecimalField(
        max_digits=12, decimal_places=2)
    risk_tolerance = serializers.ChoiceField(
        choices=[('conservative', 'Conservador'),
                 ('moderate', 'Moderado'), ('aggressive', 'Agressivo')]
    )

    # Confirmation fields
    terms_accepted = serializers.BooleanField(
        help_text="Aceito os termos e condições")
    privacy_accepted = serializers.BooleanField(
        help_text="Aceito a política de privacidade")

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError(
                "É necessário aceitar os termos e condições")
        return value

    def validate_privacy_accepted(self, value):
        if not value:
            raise serializers.ValidationError(
                "É necessário aceitar a política de privacidade")
        return value

    def create(self, validated_data):
        # Remove confirmation fields before creating investor
        validated_data.pop('terms_accepted')
        validated_data.pop('privacy_accepted')
        # This might go to a separate model
        validated_data.pop('investment_capacity')
        # This might go to a separate model
        validated_data.pop('risk_tolerance')

        # Set default values for new investor
        validated_data.update({
            'type': 'pf' if len(validated_data['document']) == 11 else 'pj',
            'kyc_status': 'pending',
            'status': 'active'
        })

        investor = Investor.objects.create(**validated_data)

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

        return investor


class InvestorCreatedSerializer(serializers.ModelSerializer):
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
    rate = serializers.DecimalField(max_digits=9, decimal_places=6)      
    band = serializers.CharField(max_length=1, allow_null=True, required=False)  
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
