#!/usr/bin/env python3
from decimal import Decimal
from consign_app.core_db.models import Borrower, LoanOffer, Contract
from django.contrib.auth.models import User
from django.test import Client
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'consign_app.settings')
django.setup()


c = Client()

username = 'debug_user'
email = 'debug_user@example.com'
password = 'testpass123'

# Clean up if exists
User.objects.filter(username=username).delete()

user = User.objects.create_user(
    username=username, email=email, password=password, first_name='Debug', last_name='User')

# Ensure borrower exists
Borrower.objects.filter(email=email).delete()
borrower = Borrower.objects.create(name='Debug User', email=email, document='00000000000',
                                   phone_number='', kyc_status='approved', credit_status='approved')

logged_in = c.login(username=username, password=password)
print('logged_in:', logged_in)

# Try two formats
for val in ['1234.56', '1.234,56']:
    print('\n--- Testing input:', val)
    resp = c.post('/loan-simulation/', {'loan_amount': val, 'loan_term': 12})
    print('post response status', resp.status_code)
    # Check session
    session = c.session
    print('session loan_amount', session.get('loan_amount'))
    offer_id = session.get('loan_offer_id')
    print('session loan_offer_id', offer_id)
    if offer_id:
        try:
            offer = LoanOffer.objects.get(offer_id=offer_id)
            print('LoanOffer.amount (DB):', offer.amount, type(offer.amount))
        except Exception as e:
            print('Could not get LoanOffer:', e)

        # Accept via API endpoint
        accept_resp = c.post(f'/api/offers/{offer.offer_id}/accept/')
        print('accept status', accept_resp.status_code)

        # Refresh and show offer
        offer.refresh_from_db()
        print('Offer status after accept:', offer.status)

        # Try to find contract
        try:
            contract = Contract.objects.filter(offer=offer).first()
            if contract:
                print('Contract principal_amount:', contract.principal_amount)
            else:
                print('No Contract created')
        except Exception as e:
            print('Error fetching contract:', e)

print('\nDone')
