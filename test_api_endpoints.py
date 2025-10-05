#!/usr/bin/env python3
"""
Comprehensive API Endpoint Testing Script
Tests all P2P platform API endpoints with OAuth2 authentication
"""

import requests
import json
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional


class P2PAPITester:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", token: str = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers.update({
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            })

        # Test data storage
        self.test_results = []
        self.created_objects = {}

    def log_test(self, endpoint: str, method: str, status_code: int,
                 success: bool, response_data: Any = None, error: str = None):
        """Log test results"""
        result = {
            'timestamp': datetime.now().isoformat(),
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'success': success,
            'error': error,
            'response_sample': str(response_data)[:200] if response_data else None
        }
        self.test_results.append(result)

        status_icon = "✅" if success else "❌"
        print(
            f"{status_icon} {method} {endpoint} - {status_code} - {'PASS' if success else 'FAIL'}")
        if error:
            print(f"   Error: {error}")

    def test_endpoint(self, endpoint: str, method: str = 'GET',
                      data: Dict = None, expected_status: int = 200) -> Optional[Dict]:
        """Test a single endpoint"""
        url = f"{self.base_url}/api/v1{endpoint}"

        try:
            if method == 'GET':
                response = self.session.get(url)
            elif method == 'POST':
                response = self.session.post(url, json=data)
            elif method == 'PUT':
                response = self.session.put(url, json=data)
            elif method == 'PATCH':
                response = self.session.patch(url, json=data)
            elif method == 'DELETE':
                response = self.session.delete(url)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            response_data = None

            try:
                response_data = response.json()
            except:
                response_data = response.text

            self.log_test(endpoint, method, response.status_code,
                          success, response_data)

            if success:
                return response_data
            else:
                self.log_test(endpoint, method, response.status_code, False,
                              response_data, f"Expected {expected_status}, got {response.status_code}")
                return None

        except Exception as e:
            self.log_test(endpoint, method, 0, False, None, str(e))
            return None

    def test_auth_endpoint(self):
        """Test authentication endpoint"""
        print("\n🔐 Testing Authentication...")
        return self.test_endpoint('/test/', 'GET')

    def test_investor_endpoints(self):
        """Test all investor-related endpoints"""
        print("\n💰 Testing Investor Endpoints...")

        # Test investor creation
        investor_data = {
            "type": "pf",
            "name": "Test Investor API",
            "document": "12345678901",
            "email": "test.investor@example.com",
            "phone_number": "+5511999999999",
            "suitability_profile": "conservative",
            "preferred_payout_method": "pix"
        }

        created_investor = self.test_endpoint(
            '/investors/', 'POST', investor_data, 201)
        if created_investor:
            investor_id = created_investor.get('investor_id')
            self.created_objects['investor_id'] = investor_id

            # Test investor offers list
            self.test_endpoint(f'/investors/{investor_id}/offers/', 'GET')

            # Test investor history
            self.test_endpoint(f'/investors/{investor_id}/history/', 'GET')

            # Test investor KYC status
            self.test_endpoint(f'/investors/{investor_id}/kyc/', 'GET')

            # Test investor KYC submission
            kyc_data = {
                "name": "Test Investor API",
                "tax_id": "12345678901",
                "email": "test.investor@example.com",
                "phone": "+5511999999999",
                "address": {
                    "street": "Test Street 123",
                    "city": "São Paulo",
                    "state": "SP",
                    "zipcode": "01234567"
                },
                "documents": [
                    {"type": "cpf", "number": "12345678901"},
                    {"type": "rg", "number": "123456789"}
                ]
            }
            self.test_endpoint(
                f'/investors/{investor_id}/kyc/submit/', 'POST', kyc_data, 202)

    def test_borrower_endpoints(self):
        """Test all borrower-related endpoints"""
        print("\n💳 Testing Borrower Endpoints...")

        # Test borrower creation
        borrower_data = {
            "name": "Test Borrower API",
            "document": "98765432100",
            "email": "test.borrower@example.com",
            "phone_number": "+5511888888888",
            "consigned_margin": "5000.00"
        }

        created_borrower = self.test_endpoint(
            '/borrowers/', 'POST', borrower_data, 201)
        if created_borrower:
            borrower_id = created_borrower.get('borrower_id')
            self.created_objects['borrower_id'] = borrower_id

            # Test borrower simulation
            simulation_data = {
                "amount": "10000.00",
                "term_months": 12,
                "disbursement_date": None
            }
            self.test_endpoint(
                f'/borrowers/{borrower_id}/simulation/', 'POST', simulation_data, 201)

            # Test borrower KYC status
            self.test_endpoint(f'/borrowers/{borrower_id}/kyc/', 'GET')

            # Test borrower KYC submission
            kyc_data = {
                "name": "Test Borrower API",
                "tax_id": "98765432100",
                "email": "test.borrower@example.com",
                "phone": "+5511888888888",
                "address": {
                    "street": "Test Avenue 456",
                    "city": "São Paulo",
                    "state": "SP",
                    "zipcode": "01234567"
                },
                "documents": [
                    {"type": "cpf", "number": "98765432100"},
                    {"type": "proof_of_income", "value": "8000.00"}
                ]
            }
            self.test_endpoint(
                f'/borrowers/{borrower_id}/kyc/submit/', 'POST', kyc_data, 202)

    def test_offer_endpoints(self):
        """Test offer-related endpoints"""
        print("\n📋 Testing Offer Endpoints...")

        # Get existing offers from database to test detail view
        offers_response = self.test_endpoint(
            '/investors/00000000-0000-0000-0000-000000000000/offers/', 'GET', expected_status=404)

        # Test offer detail with a known offer ID from the loaded data
        # Using one of the loan offer IDs from the CSV data
        # Use an offer ID present in the provided mock data (p2p_loan_offers.csv)
        test_offer_id = "69b0d174-a948-34c3-0d65-0b6e9ecb1d5f"
        self.test_endpoint(f'/offers/{test_offer_id}/', 'GET')

    def test_error_cases(self):
        """Test error handling"""
        print("\n🚨 Testing Error Cases...")

        # Test invalid endpoints
        self.test_endpoint('/invalid/', 'GET', expected_status=404)

        # Test invalid investor ID
        invalid_id = "00000000-0000-0000-0000-000000000000"
        self.test_endpoint(
            f'/investors/{invalid_id}/offers/', 'GET', expected_status=404)

        # Test invalid data
        invalid_investor_data = {
            "type": "invalid_type",
            "name": "",  # Empty name
            "document": "invalid_doc"
        }
        self.test_endpoint('/investors/', 'POST',
                           invalid_investor_data, expected_status=400)

        # Test missing authentication (temporarily remove token)
        original_headers = self.session.headers.copy()
        self.session.headers.pop('Authorization', None)
        self.test_endpoint('/test/', 'GET', expected_status=401)
        self.session.headers.update(original_headers)

    def test_all_endpoints(self):
        """Run all endpoint tests"""
        print("🚀 Starting Comprehensive API Endpoint Testing...")
        print(f"Base URL: {self.base_url}")
        print(f"Using OAuth2 Token: {'Yes' if self.token else 'No'}")

        start_time = time.time()

        # Run all test suites
        self.test_auth_endpoint()
        self.test_investor_endpoints()
        self.test_borrower_endpoints()
        self.test_offer_endpoints()
        self.test_error_cases()

        end_time = time.time()
        duration = end_time - start_time

        # Generate summary
        self.print_summary(duration)

    def print_summary(self, duration: float):
        """Print test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(
            1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests

        print("\n" + "="*60)
        print("📊 API TESTING SUMMARY")
        print("="*60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print(f"Duration: {duration:.2f} seconds")

        if self.created_objects:
            print(f"\nCreated Test Objects:")
            for key, value in self.created_objects.items():
                print(f"  {key}: {value}")

        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(
                        f"  {result['method']} {result['endpoint']} - {result['error']}")

        # Save detailed results to file
        with open('api_test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\nDetailed results saved to: api_test_results.json")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python test_api_endpoints.py <oauth_token> [base_url]")
        print("Example: python test_api_endpoints.py dl7tor4xDbTobt5FS9AUHDDN2CcjMX")
        sys.exit(1)

    token = sys.argv[1]
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"

    tester = P2PAPITester(base_url, token)
    tester.test_all_endpoints()


if __name__ == "__main__":
    main()
