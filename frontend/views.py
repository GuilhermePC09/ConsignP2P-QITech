# ===============================================
# FRONTEND VIEWS FOR BORROWER INTERFACE
# ===============================================

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings
from functools import reduce
from oauth2_provider.models import Application
from consign_app.core_db.models import Investor, Borrower, LoanOffer
from consign_app.api.serializers import InvestorUserRegistrationSerializer, BorrowerUserRegistrationSerializer
from .forms import BorrowerRegistrationForm, BorrowerLoginForm, LoanSimulationForm


def home(request):
    """Frontend home page - Main entry point"""
    applications = Application.objects.all()
    return render(request, 'frontend/home.html', {
        'applications': applications
    })


@csrf_protect
@require_http_methods(["GET", "POST"])
def register(request):
    """Borrower registration page"""
    if request.method == 'POST':
        form = BorrowerRegistrationForm(request.POST)

        if form.is_valid():
            # Prepare data for the serializer
            full_name = f"{form.cleaned_data['first_name']} {form.cleaned_data['last_name']}".strip(
            )

            data = {
                # Use email as username
                'username': form.cleaned_data['email'],
                'email': form.cleaned_data['email'],
                'password': form.cleaned_data['password1'],
                'first_name': form.cleaned_data['first_name'],
                'last_name': form.cleaned_data['last_name'],
                'name': full_name,  # Serializer expects 'name'
                'document': form.cleaned_data['cpf'],  # CPF (already cleaned)
                'phone_number': form.cleaned_data['phone_number'],
            }

            serializer = BorrowerUserRegistrationSerializer(data=data)

            if serializer.is_valid():
                result = serializer.save()

                # Check if this is part of loan application flow
                is_loan_flow = request.GET.get(
                    'flow') == 'loan' or request.POST.get('flow') == 'loan'

                if is_loan_flow:
                    messages.success(
                        request, 'Conta criada com sucesso! Vamos simular seu empréstimo.')
                    return redirect('frontend:loan_simulation')
                else:
                    messages.success(
                        request, 'Conta criada com sucesso! Bem-vindo ao QInvest.')
                    return redirect('frontend:welcome')
            else:
                # Parse serializer errors and show user-friendly messages in Portuguese
                for field, errors in serializer.errors.items():
                    for error in errors:
                        messages.error(request, f"Erro: {str(error)}")
        else:
            # Show form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form[field].label}: {error}")
    else:
        form = BorrowerRegistrationForm()

    # Check if this is part of the loan application flow
    is_loan_flow = request.GET.get('flow') == 'loan'

    return render(request, 'frontend/register.html', {
        'form': form,
        'is_loan_flow': is_loan_flow
    })


@csrf_protect
@require_http_methods(["GET", "POST"])
def login_view(request):
    """Login page"""
    login_success = False
    user = None
    user_profile = None

    if request.method == 'POST':
        form = BorrowerLoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                login_success = True

                # Try to get borrower profile
                try:
                    user_profile = Borrower.objects.get(email=user.email)
                except Borrower.DoesNotExist:
                    try:
                        user_profile = Investor.objects.get(email=user.email)
                    except Investor.DoesNotExist:
                        user_profile = None

                messages.success(
                    request, f'Bem-vindo de volta, {user.first_name}!')
            else:
                messages.error(
                    request, 'Email ou senha incorretos. Tente novamente.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form[field].label}: {error}")
    else:
        form = BorrowerLoginForm()

    return render(request, 'frontend/login.html', {
        'form': form,
        'login_success': login_success,
        'user': user,
        'user_profile': user_profile
    })


def welcome(request):
    """Welcome page with user context"""
    user_context = None
    user_type = None

    if request.user.is_authenticated:
        try:
            # Since Borrower model no longer has user field, match by email
            borrower = Borrower.objects.get(email=request.user.email)
            user_context = borrower
            user_type = 'borrower'
        except Borrower.DoesNotExist:
            # Check if this is an investor instead
            try:
                investor = Investor.objects.get(email=request.user.email)
                user_context = investor
                user_type = 'investor'
            except Investor.DoesNotExist:
                pass

    applications = Application.objects.all()
    return render(request, 'frontend/welcome.html', {
        'user_context': user_context,
        'user_type': user_type,
        'applications': applications
    })


def logout_view(request):
    """Logout user and redirect to home"""
    logout(request)
    messages.success(request, 'Você foi desconectado com sucesso.')
    return redirect('frontend:home')


@csrf_protect
@require_http_methods(["GET", "POST"])
def loan_simulation(request):
    """Step 3: Loan Simulation page"""
    if request.method == 'POST':
        form = LoanSimulationForm(request.POST)
        if form.is_valid():
            # Handle loan simulation form submission
            loan_amount = form.cleaned_data['loan_amount']
            loan_term = form.cleaned_data['loan_term']

            # Store loan simulation data in session for the proposal step
            request.session['loan_amount'] = float(loan_amount)
            request.session['loan_term'] = loan_term

            messages.success(
                request, f'Simulação realizada com sucesso! Valor: R$ {loan_amount}, Prazo: {loan_term} meses')

            # Check if user is authenticated and has documents verified
            if request.user.is_authenticated:
                try:
                    borrower = Borrower.objects.get(email=request.user.email)
                    # If documents are already verified (kyc_status is approved), skip step 4
                    if borrower.kyc_status == 'approved':
                        # TODO: Redirect to step 5 when implemented
                        messages.info(
                            request, 'Documentos já verificados. Prosseguindo para próxima etapa.')
                        # Temporary redirect until step 5 is implemented
                        return redirect('frontend:welcome')
                    else:
                        # Documents not verified, go to step 4 with source parameter
                        return redirect('frontend:document_verification_with_source', source='loan-simulation')
                except Borrower.DoesNotExist:
                    # User not found, go to document verification anyway
                    return redirect('frontend:document_verification_with_source', source='loan-simulation')
            else:
                # User not authenticated, go to document verification
                return redirect('frontend:document_verification_with_source', source='loan-simulation')
        else:
            # Form has validation errors
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = LoanSimulationForm()

    return render(request, 'frontend/loan_simulation.html', {'form': form})


@csrf_protect
@require_http_methods(["GET", "POST"])
def document_verification(request, source=None):
    """Step 4: Document Verification page"""
    if request.method == 'POST':
        # Handle document verification form submission
        messages.success(request, 'Documentos verificados com sucesso!')

        # Update borrower's KYC status if user is authenticated
        if request.user.is_authenticated:
            try:
                borrower = Borrower.objects.get(email=request.user.email)
                borrower.kyc_status = 'pending'  # Set to pending review
                borrower.save()
            except Borrower.DoesNotExist:
                pass

        # Determine redirect based on source parameter
        if source == 'loan-simulation':
            # User came from loan simulation (step 3), go to step 6 (loan proposal)
            return redirect('frontend:loan_proposal')
        else:
            # User came from somewhere else (like welcome page), return there
            return redirect('frontend:welcome')

    # Pass source to template so we can adjust the back button
    context = {
        'source': source,
        'debug_mode': settings.DEBUG,
    }
    return render(request, 'frontend/document_verification.html', context)


@csrf_protect
@require_http_methods(["GET", "POST"])
def loan_proposal(request):
    """Step 6: Loan Proposal page - Final step of loan application"""
    # Get user loan simulation data from session (if available)
    loan_amount = request.session.get('loan_amount', 5000.00)
    loan_term = request.session.get('loan_term', 24)

    # Calculate loan terms (simplified calculation)
    # 2.5% per month (this would come from your business logic)
    monthly_rate = 2.5
    monthly_payment = loan_amount * (monthly_rate/100) * (
        1 + monthly_rate/100)**loan_term / ((1 + monthly_rate/100)**loan_term - 1)
    total_payment = monthly_payment * loan_term
    annual_rate = ((1 + monthly_rate/100)**12 - 1) * \
        100  # Annual equivalent rate

    loan_data = {
        'amount': loan_amount,
        'term': loan_term,
        'monthly_rate': monthly_rate,
        'monthly_payment': monthly_payment,
        'total_payment': total_payment,
        'annual_rate': annual_rate,
    }

    if request.method == 'POST':
        # Handle loan proposal acceptance/rejection
        action = request.POST.get('action')

        if action == 'accept':
            messages.success(
                request, 'Proposta aceita! Seu empréstimo está em análise.')
            # Here you would typically create a loan application record
            # Clear session data
            request.session.pop('loan_amount', None)
            request.session.pop('loan_term', None)
            return redirect('frontend:welcome')
        elif action == 'reject':
            messages.info(
                request, 'Proposta recusada. Você pode fazer uma nova simulação a qualquer momento.')
            # Clear session data
            request.session.pop('loan_amount', None)
            request.session.pop('loan_term', None)
            return redirect('frontend:home')

    context = {
        'loan_data': loan_data
    }
    return render(request, 'frontend/loan_proposal.html', context)


@csrf_protect
@require_http_methods(["GET"])
def marketplace(request):
    """Investment marketplace for investors"""
    # Get all loan offers that are open for investment
    offers = LoanOffer.objects.filter(status='open')

    # Apply filters
    valor_min = request.GET.get('valor_min')
    valor_max = request.GET.get('valor_max')
    prazo_min = request.GET.get('prazo_min')
    prazo_max = request.GET.get('prazo_max')
    taxa_min = request.GET.get('taxa_min')
    taxa_max = request.GET.get('taxa_max')
    risco = request.GET.get('risco')
    ordenar = request.GET.get('ordenar', 'taxa_desc')

    # Apply value filters
    if valor_min:
        try:
            valor_min_clean = float(
                valor_min.replace('.', '').replace(',', '.'))
            offers = offers.filter(amount__gte=valor_min_clean)
        except (ValueError, AttributeError):
            pass

    if valor_max:
        try:
            valor_max_clean = float(
                valor_max.replace('.', '').replace(',', '.'))
            offers = offers.filter(amount__lte=valor_max_clean)
        except (ValueError, AttributeError):
            pass

    # Apply term filters
    if prazo_min:
        try:
            offers = offers.filter(term_months__gte=int(prazo_min))
        except (ValueError, TypeError):
            pass

    if prazo_max:
        try:
            offers = offers.filter(term_months__lte=int(prazo_max))
        except (ValueError, TypeError):
            pass

    # Apply rate filters (LoanOffer uses 'rate' field, not 'monthly_rate')
    if taxa_min:
        try:
            taxa_min_clean = float(taxa_min.replace(',', '.'))
            offers = offers.filter(rate__gte=taxa_min_clean)
        except (ValueError, AttributeError):
            pass

    if taxa_max:
        try:
            taxa_max_clean = float(taxa_max.replace(',', '.'))
            offers = offers.filter(rate__lte=taxa_max_clean)
        except (ValueError, AttributeError):
            pass

    # Risk level filtering - LoanOffer doesn't have risk_level field
    # We can implement basic risk assessment based on rate
    if risco:
        risk_levels = [r.strip() for r in risco.split(',') if r.strip()]
        if risk_levels:
            # Simple risk categorization based on rate
            risk_filters = []
            if 'baixo' in risk_levels:
                risk_filters.append(Q(rate__lt=2.5))  # Low risk: < 2.5%
            if 'medio' in risk_levels:
                risk_filters.append(
                    Q(rate__gte=2.5, rate__lt=4.0))  # Medium risk: 2.5% - 4%
            if 'alto' in risk_levels:
                risk_filters.append(Q(rate__gte=4.0))  # High risk: >= 4%

            if risk_filters:
                offers = offers.filter(risk_filters[0] if len(risk_filters) == 1 else
                                       reduce(lambda x, y: x | y, risk_filters))

    # Apply sorting (LoanOffer uses 'rate' field, not 'monthly_rate')
    if ordenar == 'taxa_desc':
        offers = offers.order_by('-rate')
    elif ordenar == 'taxa_asc':
        offers = offers.order_by('rate')
    elif ordenar == 'recente':
        offers = offers.order_by('-created_at')

    # Pagination
    paginator = Paginator(offers, 10)  # 10 offers per page
    page_number = request.GET.get('page')
    offers_page = paginator.get_page(page_number)

    context = {
        'offers': offers_page,
    }
    return render(request, 'frontend/marketplace.html', context)


@csrf_protect
@require_http_methods(["GET", "POST"])
def csrf_debug(request):
    """CSRF debug page to help troubleshoot CSRF issues"""
    context = {
        'request': request,
        'csrf_token': request.META.get('CSRF_COOKIE')
    }
    return render(request, 'frontend/csrf_debug.html', context)
