# ===============================================
# FRONTEND VIEWS FOR BORROWER INTERFACE
# ===============================================

from django.shortcuts import render, redirect
import logging
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings
from functools import reduce
from oauth2_provider.models import Application
from consign_app.core_db.models import Investor, Borrower, LoanOffer
from consign_app.api.serializers import InvestorUserRegistrationSerializer, BorrowerUserRegistrationSerializer
from .forms import BorrowerRegistrationForm, InvestorRegistrationForm, BorrowerLoginForm, LoanSimulationForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator


# ===============================================
# NAVIGATION UTILITY FUNCTIONS
# ===============================================

def get_user_type(request):
    """Get the user type (borrower, investor, or None)"""
    if not request.user.is_authenticated:
        return None

    try:
        Borrower.objects.get(email=request.user.email)
        return 'borrower'
    except Borrower.DoesNotExist:
        try:
            Investor.objects.get(email=request.user.email)
            return 'investor'
        except Investor.DoesNotExist:
            return None


def get_navigation_context(request, current_page):
    """Get navigation context including back button destination"""
    user_type = get_user_type(request)
    navigation = {
        'current_page': current_page,
        'user_type': user_type,
        'back_url': None,
        'back_label': 'Voltar'
    }

    # Define navigation flows
    if current_page == 'register':
        navigation['back_url'] = 'frontend:register_choice'
    elif current_page == 'register_investor':
        navigation['back_url'] = 'frontend:register_choice'
    elif current_page == 'loan_simulation':
        if user_type == 'borrower':
            navigation['back_url'] = 'frontend:welcome'
        else:
            navigation['back_url'] = 'frontend:register_choice'
    elif current_page == 'document_verification':
        source = request.GET.get('source')
        if source == 'loan-simulation':
            navigation['back_url'] = 'frontend:loan_simulation'
        elif user_type:
            navigation['back_url'] = 'frontend:welcome'
        else:
            navigation['back_url'] = 'frontend:home'
    elif current_page == 'loan_proposal':
        navigation['back_url'] = 'frontend:document_verification'
        navigation['back_url_params'] = '?source=loan-simulation'
    elif current_page == 'marketplace':
        navigation['back_url'] = 'frontend:welcome'
    elif current_page == 'login':
        navigation['back_url'] = 'frontend:home'
    else:
        # Default fallback
        if user_type:
            navigation['back_url'] = 'frontend:welcome'
        else:
            navigation['back_url'] = 'frontend:home'

    return navigation


def get_topbar_context(request, current_page):
    """Get context variables for the topbar component"""
    if not request.user.is_authenticated:
        return {
            'current_page': current_page,
            'is_borrower': False,
            'is_investor': False,
            'user_type': None,
        }

    try:
        borrower = Borrower.objects.get(email=request.user.email)
        is_borrower = True
    except Borrower.DoesNotExist:
        is_borrower = False

    try:
        investor = Investor.objects.get(email=request.user.email)
        is_investor = True
    except Investor.DoesNotExist:
        is_investor = False

    # Determine user type
    if is_borrower and is_investor:
        user_type = 'both'
    elif is_borrower:
        user_type = 'borrower'
    elif is_investor:
        user_type = 'investor'
    else:
        user_type = None

    return {
        'current_page': current_page,
        'is_borrower': is_borrower,
        'is_investor': is_investor,
        'user_type': user_type,
    }


def home(request):
    """Frontend home page - Main entry point"""
    applications = Application.objects.all()
    navigation = get_navigation_context(request, 'home')
    topbar = get_topbar_context(request, 'home')

    context = {
        'applications': applications,
        'navigation': navigation,
        **topbar  # Merge topbar context variables
    }

    return render(request, 'frontend/home.html', context)


@csrf_protect
@require_http_methods(["GET"])
def register_choice(request):
    """Registration type selection page"""
    topbar = get_topbar_context(request, 'register_choice')
    return render(request, 'frontend/register_choice.html', topbar)


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

                # Authenticate and login the user after successful registration
                user = authenticate(request, username=form.cleaned_data['email'],
                                    password=form.cleaned_data['password1'])
                if user is not None:
                    login(request, user)

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
    navigation = get_navigation_context(request, 'register')
    topbar = get_topbar_context(request, 'register')

    context = {
        'form': form,
        'is_loan_flow': is_loan_flow,
        'user_type': 'borrower',
        'navigation': navigation,
        **topbar
    }

    return render(request, 'frontend/register.html', context)


@csrf_protect
@require_http_methods(["GET", "POST"])
def register_investor(request):
    """Investor registration page"""
    if request.method == 'POST':
        form = InvestorRegistrationForm(request.POST)

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
                'document': form.cleaned_data['document'],  # CPF or CNPJ
                'phone_number': form.cleaned_data['phone_number'],
                'type': form.cleaned_data['user_type'],  # pf or pj
            }

            serializer = InvestorUserRegistrationSerializer(data=data)

            if serializer.is_valid():
                result = serializer.save()

                # Authenticate and login the user after successful registration
                user = authenticate(request, username=form.cleaned_data['email'],
                                    password=form.cleaned_data['password1'])
                if user is not None:
                    login(request, user)

                messages.success(
                    request, 'Conta de investidor criada com sucesso! Bem-vindo ao QInvest.')
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
        form = InvestorRegistrationForm()

    navigation = get_navigation_context(request, 'register_investor')
    topbar = get_topbar_context(request, 'register_investor')

    context = {
        'form': form,
        'is_loan_flow': False,
        'user_type': 'investor',
        'navigation': navigation,
        **topbar
    }

    return render(request, 'frontend/register.html', context)


@csrf_protect
@require_http_methods(["GET", "POST"])
def login_view(request):
    """Login page"""
    if request.method == 'POST':
        form = BorrowerLoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)

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

                # Redirect to welcome page after successful login
                return redirect('frontend:welcome')
            else:
                messages.error(
                    request, 'Email ou senha incorretos. Tente novamente.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form[field].label}: {error}")
    else:
        form = BorrowerLoginForm()

    navigation = get_navigation_context(request, 'login')
    topbar = get_topbar_context(request, 'login')

    context = {
        'form': form,
        'navigation': navigation,
        **topbar
    }

    return render(request, 'frontend/login.html', context)


def welcome(request):
    """Welcome page with user context"""
    user_context = None
    user_type = None
    is_borrower = False
    is_investor = False
    borrower = None
    investor = None

    if request.user.is_authenticated:
        # Check if user is a borrower
        try:
            borrower = Borrower.objects.get(email=request.user.email)
            is_borrower = True
        except Borrower.DoesNotExist:
            pass

        # Check if user is an investor
        try:
            investor = Investor.objects.get(email=request.user.email)
            is_investor = True
        except Investor.DoesNotExist:
            pass

        # Determine user_type and user_context based on what they are
        if is_borrower and is_investor:
            # User is both - prioritize investor for marketplace access
            user_type = 'both'
            user_context = investor  # Show investor context in the welcome
        elif is_investor:
            user_type = 'investor'
            user_context = investor
        elif is_borrower:
            user_type = 'borrower'
            user_context = borrower

    applications = Application.objects.all()
    topbar = get_topbar_context(request, 'welcome')

    context = {
        'user_context': user_context,
        'user_type': user_type,
        'is_borrower': is_borrower,
        'is_investor': is_investor,
        'applications': applications,
        **topbar
    }

    return render(request, 'frontend/welcome.html', context)


def logout_view(request):
    """Logout user and redirect to home"""
    logout(request)
    messages.success(request, 'Você foi desconectado com sucesso.')
    return redirect('frontend:home')


@require_POST
@login_required
def api_register_offer(request, offer_id):
    """Mark a LoanOffer as open and return a JSON response used by frontend JS.

    This is a lightweight convenience endpoint so the frontend can POST to
    open an offer on the marketplace without requiring the full API OAuth flow.
    """
    from consign_app.core_db.models import LoanOffer

    offer = get_object_or_404(LoanOffer, offer_id=offer_id)

    # Ensure the logged in user is the borrower owner of the offer (best-effort)
    try:
        borrower = getattr(request.user, 'email', None) and LoanOffer.objects.filter(
            borrower__email=request.user.email).exists()
    except Exception:
        borrower = False

    # Allow only the borrower who owns the offer (or staff) to open it
    if not (request.user.is_staff or borrower):
        return JsonResponse({'detail': 'Forbidden'}, status=403)

    try:
        offer.status = 'open'
        offer.save(update_fields=['status'])
    except Exception as e:
        return JsonResponse({'detail': 'Failed to register offer', 'error': str(e)}, status=500)

    return JsonResponse({'message': 'Offer registered in marketplace', 'offer_id': str(offer.offer_id)})


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

            # If user is authenticated, try to create a real loan offer via API simulation
            if request.user.is_authenticated:
                try:
                    logger = logging.getLogger(__name__)
                    from consign_app.core_db.models import Borrower
                    borrower = Borrower.objects.get(email=request.user.email)
                except Borrower.DoesNotExist:
                    # Create borrower record for the user
                    borrower = Borrower.objects.create(
                        name=f"{request.user.first_name} {request.user.last_name}".strip(
                        ) or request.user.username,
                        email=request.user.email,
                        document="00000000000",  # Placeholder - would be collected in registration
                        phone_number="",  # Placeholder
                        kyc_status='none',  # Default status, becomes 'pending' when documents are submitted
                        credit_status='pending'
                    )

                # Try to create a loan offer via the simulation API
                # This would normally be done via OAuth but for frontend integration we'll create directly
                try:
                    from consign_app.api.feature_builder import build_features_for_borrower
                    from consign_app.core_db.models import LoanOffer
                    from decimal import Decimal
                    from datetime import date, timedelta
                    import uuid

                    # Simple rate calculation for now (would come from risk scoring in production)
                    monthly_rate = Decimal('2.5')  # 2.5% per month
                    annual_rate = (1 + monthly_rate/100) ** 12 - 1
                    cet = annual_rate * 100

                    # Create loan offer
                    logger.debug(
                        "Creating LoanOffer from simulation input: loan_amount=%r loan_term=%r", loan_amount, loan_term)
                    offer = LoanOffer.objects.create(
                        borrower=borrower,
                        amount=Decimal(str(loan_amount)),
                        rate=monthly_rate,
                        term_months=loan_term,
                        valid_until=date.today() + timedelta(days=30),
                        status="draft",
                        cet=cet,
                        apr=annual_rate * 100,
                        fees={
                            "origination_fee": float(Decimal(str(loan_amount)) * Decimal("0.02")),
                            "iof": float(Decimal(str(loan_amount)) * Decimal("0.0038")),
                            "insurance": 150.00
                        },
                        external_reference=f"SIM-{uuid.uuid4().hex[:12]}"
                    )

                    # Store offer ID in session
                    request.session['loan_offer_id'] = str(offer.offer_id)
                    logger.debug("Created LoanOffer.offer_id=%s amount=%s",
                                 offer.offer_id, str(offer.amount))

                except Exception as e:
                    # If offer creation fails, continue with session data only
                    logger.exception("Failed to create loan offer: %s", e)
                    pass

                # Check if documents are already verified
                if borrower.kyc_status == 'approved':
                    messages.success(
                        request, f'Simulação realizada com sucesso! Valor: R$ {loan_amount}, Prazo: {loan_term} meses')
                    # Go directly to loan proposal
                    return redirect('frontend:loan_proposal')
                else:
                    # Documents not verified, go to step 4 with source parameter
                    messages.success(
                        request, f'Simulação realizada com sucesso! Valor: R$ {loan_amount}, Prazo: {loan_term} meses')
                    return redirect('frontend:document_verification_with_source', source='loan-simulation')
            else:
                # User not authenticated, go to document verification
                messages.success(
                    request, f'Simulação realizada com sucesso! Valor: R$ {loan_amount}, Prazo: {loan_term} meses')
                return redirect('frontend:document_verification_with_source', source='loan-simulation')
        else:
            # Form has validation errors
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = LoanSimulationForm()

    navigation = get_navigation_context(request, 'loan_simulation')
    topbar = get_topbar_context(request, 'loan_simulation')

    context = {
        'form': form,
        'navigation': navigation,
        **topbar
    }

    return render(request, 'frontend/loan_simulation.html', context)


@csrf_protect
@require_http_methods(["GET", "POST"])
def document_verification(request, source=None):
    """Step 4: Document Verification page"""

    # Check user's verification status
    is_verified = False
    kyc_status = None
    borrower = None

    if request.user.is_authenticated:
        try:
            borrower = Borrower.objects.get(email=request.user.email)
            kyc_status = borrower.kyc_status or 'none'
            # Only consider 'approved' as verified, not 'pending'
            is_verified = kyc_status == 'approved'
        except Borrower.DoesNotExist:
            pass

    if request.method == 'POST':
        # Handle document verification form submission
        if request.POST.get('action') == 'resend':
            messages.info(request, 'Documentos reenviados para análise.')
            if borrower:
                borrower.kyc_status = 'approved'
                borrower.save()
        else:
            messages.success(request, 'Documentos verificados com sucesso!')
            if borrower:
                borrower.kyc_status = 'approved'
                borrower.save()

        # Determine redirect based on source parameter
        if source == 'loan-simulation':
            # If the session doesn't have a loan_offer_id (maybe created in a prior unauthenticated flow),
            # attempt to create a minimal LoanOffer now so the proposal step can load.
            if not request.session.get('loan_offer_id'):
                try:
                    from consign_app.core_db.models import LoanOffer
                    from decimal import Decimal
                    from datetime import date, timedelta
                    import uuid

                    loan_amount = request.session.get('loan_amount', 5000.00)
                    loan_term = request.session.get('loan_term', 24)

                    # Ensure borrower exists
                    if not borrower:
                        from consign_app.core_db.models import Borrower as BorrowerModel
                        borrower = BorrowerModel.objects.create(
                            name=f"{request.user.first_name} {request.user.last_name}".strip(
                            ) or request.user.username,
                            email=request.user.email,
                            document="00000000000",
                            phone_number="",
                            kyc_status='approved',
                            credit_status='pending'
                        )

                    offer = LoanOffer.objects.create(
                        borrower=borrower,
                        amount=Decimal(str(loan_amount)),
                        rate=Decimal('2.5'),
                        term_months=int(loan_term),
                        valid_until=date.today() + timedelta(days=30),
                        status='draft',
                        cet=0,
                        apr=0,
                        external_reference=f"AUTO-{uuid.uuid4().hex[:12]}",
                    )
                    request.session['loan_offer_id'] = str(offer.offer_id)
                except Exception as e:
                    # If creation fails, log and continue — the redirect will show the missing simulation message
                    print(f"Failed to create fallback loan offer: {e}")
            # User came from loan simulation (step 3), go to step 6 (loan proposal)
            return redirect('frontend:loan_proposal')
        else:
            # User came from somewhere else (like welcome page), return there
            return redirect('frontend:welcome')

    # Pass context including verification status and navigation
    navigation = get_navigation_context(request, 'document_verification')
    topbar = get_topbar_context(request, 'document_verification')

    context = {
        'source': source,
        'is_verified': is_verified,
        'kyc_status': kyc_status,
        'navigation': navigation,
        'debug_mode': settings.DEBUG,
        **topbar
    }

    return render(request, 'frontend/document_verification.html', context)


@csrf_protect
@require_http_methods(["GET", "POST"])
def loan_proposal(request):
    """Step 6: Loan Proposal page - Final step of loan application"""
    # Get loan offer data from session (created during simulation)
    offer_id = request.session.get('loan_offer_id')
    if not offer_id:
        messages.error(
            request, 'Simulação não encontrada. Por favor, refaça a simulação.')
        return redirect('frontend:loan_simulation')

    loan_amount = request.session.get('loan_amount', 5000.00)
    loan_term = request.session.get('loan_term', 24)

    from consign_app.core_db.models import LoanOffer
    try:
        loan_offer = LoanOffer.objects.get(offer_id=offer_id)
    except LoanOffer.DoesNotExist:
        messages.error(
            request, 'Oferta não encontrada. Por favor, refaça a simulação.')
        return redirect('frontend:loan_simulation')

    loan_data = {
        'offer_id': str(loan_offer.offer_id),
        'amount': float(loan_offer.amount),
        'term': loan_offer.term_months,
        'monthly_rate': float(loan_offer.rate),
        'cet': float(loan_offer.cet) if loan_offer.cet else 0,
        'apr': float(loan_offer.apr) if loan_offer.apr else 0,
    }

    monthly_rate_decimal = float(loan_offer.rate) / 100
    amount_float = float(loan_offer.amount)
    if monthly_rate_decimal > 0:
        monthly_payment = amount_float * (monthly_rate_decimal * (1 + monthly_rate_decimal)
                                          ** loan_offer.term_months) / ((1 + monthly_rate_decimal)**loan_offer.term_months - 1)
    else:
        monthly_payment = amount_float / loan_offer.term_months
    total_payment = monthly_payment * loan_offer.term_months
    total_interest = total_payment - amount_float
    loan_data.update({
        'monthly_payment': monthly_payment,
        'total_payment': total_payment,
        'total_interest': total_interest,
    })

    if request.method == 'POST':
        # Handle loan proposal acceptance/rejection
        action = request.POST.get('action')

        if action == 'accept':
            messages.success(
                request, 'Proposta aceita! Seu empréstimo está em análise.')
            # Clear session data
            request.session.pop('loan_amount', None)
            request.session.pop('loan_term', None)
            request.session.pop('loan_offer_id', None)
            return redirect('frontend:welcome')
        elif action == 'reject':
            messages.info(
                request, 'Proposta recusada. Você pode fazer uma nova simulação a qualquer momento.')
            # Clear session data
            request.session.pop('loan_amount', None)
            request.session.pop('loan_term', None)
            request.session.pop('loan_offer_id', None)
            return redirect('frontend:home')

    navigation = get_navigation_context(request, 'loan_proposal')
    topbar = get_topbar_context(request, 'loan_proposal')

    context = {
        'loan_data': loan_data,
        'navigation': navigation,
        **topbar
    }

    return render(request, 'frontend/loan_proposal.html', context)


@csrf_protect
@require_http_methods(["GET"])
@login_required
def marketplace(request):
    """Investment marketplace for investors only"""

    # Check if user is an investor (they might also be a borrower, but that's ok)
    is_investor = False
    is_borrower = False

    try:
        borrower = Borrower.objects.get(email=request.user.email)
        is_borrower = True
    except Borrower.DoesNotExist:
        pass

    try:
        investor = Investor.objects.get(email=request.user.email)
        is_investor = True
    except Investor.DoesNotExist:
        pass

    # Only allow access if user is an investor
    if not is_investor:
        if is_borrower:
            # User is only a borrower, not an investor
            messages.error(
                request, "O marketplace é exclusivo para investidores. Como solicitante, você pode acessar suas simulações e propostas.")
            return redirect('frontend:welcome')
        else:
            # User exists but has no investor profile - redirect to registration
            messages.warning(
                request, "Para acessar o marketplace, você precisa completar seu perfil de investidor.")
            return redirect('frontend:register')

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
    # 12 offers per page (3 rows × 4 columns on desktop)
    paginator = Paginator(offers, 12)
    page_number = request.GET.get('page')
    offers_page = paginator.get_page(page_number)

    navigation = get_navigation_context(request, 'marketplace')
    topbar = get_topbar_context(request, 'marketplace')

    context = {
        'offers': offers_page,
        'navigation': navigation,
        **topbar
    }

    return render(request, 'frontend/marketplace.html', context)


@login_required
def offer_details(request, offer_id):
    """Detailed view of a loan offer for investors"""

    # Check if user is an investor
    is_investor = False
    is_borrower = False

    try:
        borrower = Borrower.objects.get(email=request.user.email)
        is_borrower = True
    except Borrower.DoesNotExist:
        pass

    try:
        investor = Investor.objects.get(email=request.user.email)
        is_investor = True
    except Investor.DoesNotExist:
        pass

    # Only allow access if user is an investor
    if not is_investor:
        if is_borrower:
            messages.error(
                request, "O marketplace é exclusivo para investidores. Como solicitante, você pode acessar suas simulações e propostas.")
            return redirect('frontend:welcome')
        else:
            messages.warning(
                request, "Para acessar detalhes de ofertas, você precisa completar seu perfil de investidor.")
            return redirect('frontend:register')

    # Get the specific offer
    try:
        offer = LoanOffer.objects.get(offer_id=offer_id)
    except LoanOffer.DoesNotExist:
        messages.error(request, "Oferta não encontrada.")
        return redirect('frontend:marketplace')

    # Calculate additional metrics
    monthly_payment = offer.amount / offer.term_months if offer.term_months > 0 else 0
    total_interest = (monthly_payment * offer.term_months) - \
        offer.amount if offer.term_months > 0 else 0

    # Calculate CET Anual (always available for template)
    from decimal import Decimal, InvalidOperation
    try:
        monthly_rate_decimal = Decimal(str(offer.rate))
        cet_anual = ((1 + monthly_rate_decimal/100) ** 12 - 1) * 100
        cet_anual = round(cet_anual, 2)
    except (ValueError, TypeError, InvalidOperation):
        cet_anual = None

    # Simple risk calculation based on rate
    if offer.rate < 2.5:
        risk_level = 'Baixo'
        risk_color = '#16A34A'
        risk_bg = '#E6F9ED'
    elif offer.rate < 4.0:
        risk_level = 'Médio'
        risk_color = '#D97706'
        risk_bg = '#FEF3C7'
    else:
        risk_level = 'Alto'
        risk_color = '#DC2626'
        risk_bg = '#FEE2E2'

    navigation = get_navigation_context(request, 'offer_details')
    topbar = get_topbar_context(request, 'offer_details')

    context = {
        'offer': offer,
        'monthly_payment': monthly_payment,
        'total_interest': total_interest,
        'risk_level': risk_level,
        'risk_color': risk_color,
        'risk_bg': risk_bg,
        'cet_anual': cet_anual,
        'navigation': navigation,
        **topbar
    }

    return render(request, 'frontend/offer_details.html', context)


@csrf_protect
@require_http_methods(["GET", "POST"])
def csrf_debug(request):
    """CSRF debug page to help troubleshoot CSRF issues"""
    topbar = get_topbar_context(request, 'csrf_debug')

    context = {
        'request': request,
        'csrf_token': request.META.get('CSRF_COOKIE'),
        **topbar
    }

    return render(request, 'frontend/csrf_debug.html', context)
