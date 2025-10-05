#!/usr/bin/env python3

"""
Test script to verify the loan proposal frontend-backend integration
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from consign_app.core_db.models import Borrower, LoanOffer
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings
import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'consign_app.settings')
django.setup()


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
class LoanProposalIntegrationTest(TestCase):
    """Test the complete loan proposal flow"""

    def setUp(self):
        """Set up test data"""
        # Generate unique test identifiers
        import time
        test_id = str(int(time.time()))
        self.username = f'testuser_{test_id}'
        self.email = f'test_{test_id}@example.com'

        # Create test user
        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password='testpass123'
        )

        # Create test borrower
        self.borrower = Borrower.objects.create(
            name='Test Borrower',
            email=self.email,
            document='12345678901',
            phone_number='11999999999',
            kyc_status='approved',
            credit_status='approved'
        )

        # Create test loan offer
        self.offer = LoanOffer.objects.create(
            borrower=self.borrower,
            amount=Decimal('10000.00'),
            rate=Decimal('2.5'),
            term_months=24,
            valid_until=date.today() + timedelta(days=30),
            status="draft",
            cet=Decimal('34.49'),
            apr=Decimal('34.49'),
            external_reference=f"TEST-{uuid.uuid4().hex[:12]}"
        )

        self.client = Client()

    def test_complete_loan_flow(self):
        """Test the complete loan proposal flow"""
        print("🔄 Testing loan proposal integration...")

        # Test 1: Login
        print("1️⃣ Testing user login...")
        login_response = self.client.login(
            username=self.username, password='testpass123')
        self.assertTrue(login_response, "User login failed")
        print("✅ Login successful")

        # Test 2: Loan simulation
        print("2️⃣ Testing loan simulation...")
        simulation_data = {
            'loan_amount': '10,000.00',
            'loan_term': 24
        }
        simulation_response = self.client.post(
            '/loan-simulation/', simulation_data)
        self.assertIn(simulation_response.status_code, [200, 302],
                      f"Simulation failed with status {simulation_response.status_code}")
        print("✅ Loan simulation successful")

        # Test 3: Access loan proposal page
        print("3️⃣ Testing loan proposal page...")
        # Set up session data
        session = self.client.session
        session['loan_amount'] = 10000.00
        session['loan_term'] = 24
        session['loan_offer_id'] = str(self.offer.offer_id)
        session.save()

        proposal_response = self.client.get('/loan-proposal/')
        self.assertEqual(proposal_response.status_code, 200,
                         f"Proposal page failed with status {proposal_response.status_code}")
        print("✅ Loan proposal page accessible")

        # Test 4: Test download proposal
        print("4️⃣ Testing proposal download...")
        download_response = self.client.get(
            f'/api/offers/{self.offer.offer_id}/download/')
        self.assertEqual(download_response.status_code, 200,
                         f"Download failed with status {download_response.status_code}")
        self.assertIn('text/plain', download_response.get('Content-Type', ''),
                      "Download response is not text")
        print("✅ Proposal download successful")

        # Test 5: Test loan acceptance
        print("5️⃣ Testing loan acceptance...")
        accept_response = self.client.post(
            f'/api/offers/{self.offer.offer_id}/accept/')
        self.assertEqual(accept_response.status_code, 201,
                         f"Accept failed with status {accept_response.status_code}")

        # Verify offer status changed
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.status, 'accepted',
                         f"Offer status is {self.offer.status}, expected 'accepted'")
        print("✅ Loan acceptance successful")

        print("🎉 All tests passed! Frontend-backend integration is working correctly.")


def run_test():
    """Run the test using Django's test runner"""
    from django.test.utils import get_runner
    from django.conf import settings

    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["__main__"])
    return failures


if __name__ == '__main__':
    try:
        # Import django test runner
        from django.test.utils import get_runner
        from django.conf import settings
        import unittest

        # Create a test suite
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(LoanProposalIntegrationTest)

        # Run the tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        if result.wasSuccessful():
            print("\n🎉 All tests passed!")
            sys.exit(0)
        else:
            print(f"\n❌ {len(result.failures)} test(s) failed")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
