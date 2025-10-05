from django import forms
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal, InvalidOperation
from consign_app.api.serializers import validate_cpf


class BrazilianDecimalField(forms.DecimalField):
    """Custom DecimalField that accepts Brazilian number format (1.500,00)"""

    def to_python(self, value):
        """Convert value to Python decimal, handling Brazilian format"""
        if value in self.empty_values:
            return None

        if isinstance(value, str):
            # Handle different formats:
            # Brazilian: 1.500,00 or 1500,00 (comma as decimal separator)
            # English: 1500.00 or 1,500.00 (dot as decimal separator)

            # Check if it's Brazilian format (ends with comma and exactly 2 digits)
            if ',' in value and value.count(',') == 1:
                parts = value.split(',')
                if len(parts) == 2 and len(parts[1]) == 2 and parts[1].isdigit():
                    # Brazilian format: remove thousand separators (dots), then replace comma with dot
                    value = parts[0].replace('.', '') + '.' + parts[1]
                elif ',' in value and '.' in value:
                    # English format with thousand separators (like 1,500.00)
                    # Remove commas (thousand separators), keep dot as decimal
                    value = value.replace(',', '')
                # If comma but not fitting Brazilian pattern, try as-is
            # If it's English format with thousand separators but no comma as decimal
            elif ',' in value and '.' in value:
                # Remove commas (thousand separators), keep dot as decimal
                value = value.replace(',', '')
            # Otherwise, assume it's already in correct format

        try:
            return Decimal(value)
        except (ValueError, InvalidOperation):
            raise forms.ValidationError(
                'Digite um valor válido',
                code='invalid',
            )


class BorrowerRegistrationForm(forms.Form):
    """Form for borrower registration"""
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'placeholder': 'Digite seu primeiro nome',
            'required': True
        }),
        label='Primeiro Nome'
    )

    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'placeholder': 'Digite seu sobrenome',
            'required': True
        }),
        label='Sobrenome'
    )

    cpf = forms.CharField(
        max_length=14,
        widget=forms.TextInput(attrs={
            'placeholder': '000.000.000-00',
            'inputmode': 'numeric',
            'required': True
        }),
        label='CPF'
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'seu@email.com',
            'required': True
        }),
        label='E-mail'
    )

    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': '(11) 99999-9999',
            'required': True
        }),
        label='Telefone'
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Digite sua senha',
            'required': True
        }),
        label='Senha'
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirme sua senha',
            'required': True
        }),
        label='Confirmar Senha'
    )

    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        if cpf and not validate_cpf(cpf):
            raise forms.ValidationError('CPF inválido')
        return cpf

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('As senhas não conferem')
        return password2

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este e-mail já está sendo usado')
        return email


class LoanSimulationForm(forms.Form):
    """Form for loan simulation with proper validation"""
    loan_amount = BrazilianDecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('500.00'),
                              message="Valor mínimo é R$ 500,00"),
            MaxValueValidator(Decimal('10000.00'),
                              message="Valor máximo é R$ 10.000,00")
        ],
        widget=forms.TextInput(attrs={
            'placeholder': '500,00',
            'inputmode': 'numeric',
            'required': True,
            'class': 'big'
        }),
        label='Valor',
        error_messages={
            'invalid': 'Digite um valor válido',
            'required': 'Este campo é obrigatório'
        }
    )

    loan_term = forms.IntegerField(
        validators=[
            MinValueValidator(1, message="Prazo mínimo é 1 mês"),
            MaxValueValidator(96, message="Prazo máximo é 96 meses")
        ],
        widget=forms.NumberInput(attrs={
            'placeholder': '1',
            'min': '1',
            'max': '96',
            'required': True,
            'class': 'big'
        }),
        label='Meses',
        error_messages={
            'invalid': 'Digite um número válido de meses',
            'required': 'Este campo é obrigatório'
        }
    )

    def clean_loan_amount(self):
        loan_amount = self.cleaned_data.get('loan_amount')
        if loan_amount:
            if loan_amount < Decimal('500.00'):
                raise forms.ValidationError("Valor mínimo é R$ 500,00")
            if loan_amount > Decimal('10000.00'):
                raise forms.ValidationError("Valor máximo é R$ 10.000,00")
        return loan_amount

    def clean_loan_term(self):
        loan_term = self.cleaned_data.get('loan_term')
        if loan_term:
            if loan_term < 1:
                raise forms.ValidationError("Prazo mínimo é 1 mês")
            if loan_term > 96:
                raise forms.ValidationError("Prazo máximo é 96 meses")
        return loan_term


class BorrowerLoginForm(forms.Form):
    """Form for borrower login"""
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'seu@email.com',
            'required': True
        }),
        label='E-mail'
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Digite sua senha',
            'required': True
        }),
        label='Senha'
    )


class InvestorRegistrationForm(forms.Form):
    """Form for investor registration"""
    TYPE_CHOICES = [
        ('pf', 'Pessoa Física'),
        ('pj', 'Pessoa Jurídica'),
    ]

    user_type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        widget=forms.Select(attrs={
            'required': True
        }),
        label='Tipo de Pessoa'
    )

    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'placeholder': 'Digite seu primeiro nome',
            'required': True
        }),
        label='Primeiro Nome'
    )

    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'placeholder': 'Digite seu sobrenome',
            'required': True
        }),
        label='Sobrenome'
    )

    document = forms.CharField(
        max_length=18,
        widget=forms.TextInput(attrs={
            'placeholder': '000.000.000-00 ou 00.000.000/0001-00',
            'inputmode': 'numeric',
            'required': True
        }),
        label='CPF ou CNPJ'
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'seu@email.com',
            'required': True
        }),
        label='E-mail'
    )

    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': '(11) 99999-9999',
            'required': True
        }),
        label='Telefone'
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Digite sua senha',
            'required': True
        }),
        label='Senha'
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirme sua senha',
            'required': True
        }),
        label='Confirmar Senha'
    )

    def clean_document(self):
        document = self.cleaned_data.get('document')
        user_type = self.cleaned_data.get('user_type')

        if document and user_type:
            # Remove formatting characters
            clean_doc = ''.join(filter(str.isdigit, document))

            if user_type == 'pf':
                # CPF validation
                if len(clean_doc) != 11:
                    raise forms.ValidationError('CPF deve ter 11 dígitos')
                if not validate_cpf(document):
                    raise forms.ValidationError('CPF inválido')
            elif user_type == 'pj':
                # Basic CNPJ validation (14 digits)
                if len(clean_doc) != 14:
                    raise forms.ValidationError('CNPJ deve ter 14 dígitos')

        return document

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('As senhas não conferem')
        return password2

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este e-mail já está sendo usado')
        return email
