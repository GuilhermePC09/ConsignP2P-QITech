"""
Django REST API Test Suite for P2P Platform
Comprehensive tests for all API endpoints using Django's testing framework
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from oauth2_provider.models import Application, AccessToken
from decimal import Decimal
import json
import uuid

from consign_app.core_db.models import (
    Investor, Borrower, LoanOffer, Contract, Installment,
    Payment, KycRisk, Wallet, ConsignmentAgreement
)


class APITestSetup(APITestCase):
    """Base test class with OAuth2 setup"""

    def setUp(self):
        """Set up test environment with OAuth2 authentication"""
        # Create OAuth2 application
        self.application = Application.objects.create(
            name="Test Application",
            user=None,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

        # Create access token
        from django.utils import timezone
        from datetime import timedelta

        self.access_token = AccessToken.objects.create(
            user=None,
            scope='read write',
            expires=timezone.now() + timedelta(hours=1),
            token='test_token_123456789',
            application=self.application
        )

        # Set up API client with authentication
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer test_token_123456789')

        # Create test data
        self.create_test_data()

    def create_test_data(self):
        """Create test data for API testing"""
        # Create test wallet
        self.test_wallet = Wallet.objects.create(
            owner_type='platform',
            currency='BRL',
            available_balance=Decimal('100000.00')
        )

        # Create test investor
        self.test_investor = Investor.objects.create(
            type='pf',
            name='Test Investor',
            document='12345678901',
            email='investor@test.com',
            phone_number='+5511999999999',
            kyc_status='approved',
            suitability_profile='conservative',
            preferred_payout_method='pix',
            status='active',
            primary_wallet=self.test_wallet
        )

        # Create test borrower
        self.test_borrower = Borrower.objects.create(
            name='Test Borrower',
            document='98765432100',
            email='borrower@test.com',
            phone_number='+5511888888888',
            kyc_status='approved',
            credit_status='approved',
            risk_score=Decimal('0.85'),
            consigned_margin=Decimal('5000.00')
        )

        # Create test loan offer
        self.test_offer = LoanOffer.objects.create(
            borrower=self.test_borrower,
            amount=Decimal('10000.00'),
            rate=Decimal('2.50'),
            term_months=12,
            status='open',
            cet=Decimal('2.75'),
            apr=Decimal('35.00')
        )


class AuthenticationAPITest(APITestSetup):
    """Test authentication endpoints"""

    def test_auth_endpoint_success(self):
        """Test successful authentication"""
        url = reverse('test_auth')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertTrue(response.data['access_granted'])

    def test_auth_endpoint_without_token(self):
        """Test authentication failure without token"""
        client = APIClient()  # No authentication
        url = reverse('test_auth')
        response = client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class InvestorAPITest(APITestSetup):
    """Test investor-related endpoints"""

    def test_investor_create_success(self):
        """Test successful investor creation"""
        url = reverse('investor_create')
        data = {
            'type': 'pf',
            'name': 'New Test Investor',
            'document': '11122233344',
            'email': 'new.investor@test.com',
            'phone_number': '+5511777777777',
            'suitability_profile': 'aggressive',
            'preferred_payout_method': 'ted'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('investor_id', response.data)
        self.assertEqual(response.data['name'], data['name'])
        self.assertEqual(response.data['document'], data['document'])

        # Verify investor was created in database
        investor_id = response.data['investor_id']
        investor = Investor.objects.get(investor_id=investor_id)
        self.assertEqual(investor.name, data['name'])

    def test_investor_create_invalid_data(self):
        """Test investor creation with invalid data"""
        url = reverse('investor_create')
        data = {
            'type': 'invalid_type',
            'name': '',  # Empty name
            'document': '123',  # Invalid document
            'email': 'invalid_email'
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_investor_list_offers(self):
        """Test listing offers for investor"""
        url = reverse('investor_list_offers', kwargs={
                      'investor_id': str(self.test_investor.investor_id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_investor_list_offers_not_found(self):
        """Test listing offers for non-existent investor"""
        invalid_id = str(uuid.uuid4())
        url = reverse('investor_list_offers', kwargs={
                      'investor_id': invalid_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BorrowerAPITest(APITestSetup):
    """Test borrower-related endpoints"""

    def test_borrower_create_success(self):
        """Test successful borrower creation"""
        url = reverse('borrower_create')
        data = {
            'name': 'New Test Borrower',
            'document': '55566677788',
            'email': 'new.borrower@test.com',
            'phone_number': '+5511666666666',
            'consigned_margin': '3000.00'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('borrower_id', response.data)
        self.assertEqual(response.data['name'], data['name'])

        # Verify borrower was created in database
        borrower_id = response.data['borrower_id']
        borrower = Borrower.objects.get(borrower_id=borrower_id)
        self.assertEqual(borrower.name, data['name'])


class OfferAPITest(APITestSetup):
    """Test offer-related endpoints"""

    def test_offer_detail(self):
        """Test offer detail endpoint"""
        url = reverse('investor_get_offer', kwargs={
                      'offer_id': str(self.test_offer.offer_id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['offer_id'],
                         str(self.test_offer.offer_id))
        self.assertEqual(response.data['amount'], str(self.test_offer.amount))

    def test_offer_detail_not_found(self):
        """Test offer detail for non-existent offer"""
        invalid_id = str(uuid.uuid4())
        url = reverse('investor_get_offer', kwargs={'offer_id': invalid_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
