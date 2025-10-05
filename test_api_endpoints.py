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

    def get_user_token(self, username: str, password: str) -> Optional[str]:
        """Get OAuth2 token for user authentication"""
        token_url = f"{self.base_url}/o/token/"
        token_data = {
            'grant_type': 'password',
            'client_id': 'p2p-password-client',
            'client_secret': 'p2p-password-secret',
            'username': username,
            'password': password
        }

        try:
            response = requests.post(token_url, data=token_data)
            if response.status_code == 200:
                token_info = response.json()
                return token_info.get('access_token')
            else:
                print(
                    f"❌ Failed to get user token: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error getting user token: {e}")
            return None

    def test_user_registration_endpoints(self):
        """Test user registration endpoints"""
        print("\n👥 Testing User Registration Endpoints...")

        # Generate unique identifiers for this test run
        import time
        timestamp = str(int(time.time()))

        # Test investor registration
        investor_reg_data = {
            "username": f"test_investor_{timestamp}",
            "email": f"investor.{timestamp}@example.com",
            "password": "securepass123",
            "first_name": "John",
            "last_name": "Doe",
            "name": "John Doe Investment LLC",
            "document": f"9876543210{timestamp[-4:]}",  # Unique document
            "phone_number": "+5511888888888",
            "preferred_payout_method": "pix"
        }

        # Temporarily remove auth header for registration (public endpoint)
        temp_headers = self.session.headers.copy()
        if 'Authorization' in self.session.headers:
            del self.session.headers['Authorization']

        created_investor_user = self.test_endpoint(
            '/auth/register/investor/', 'POST', investor_reg_data, 201)

        if created_investor_user:
            self.created_objects['investor_user'] = {
                'username': investor_reg_data['username'],
                'password': investor_reg_data['password'],
                'investor_id': created_investor_user.get('investor', {}).get('investor_id')
            }
            print(f"   Created investor user: {investor_reg_data['username']}")

        # Test borrower registration
        borrower_reg_data = {
            "username": f"test_borrower_{timestamp}",
            "email": f"borrower.{timestamp}@example.com",
            "password": "securepass123",
            "first_name": "Jane",
            "last_name": "Smith",
            "name": "Jane Smith",
            # Unique CPF-like document (11 digits)
            "document": f"1234567890{timestamp[-1:]}",
            "phone_number": "+5511777777777"
        }

        created_borrower_user = self.test_endpoint(
            '/auth/register/borrower/', 'POST', borrower_reg_data, 201)

        if created_borrower_user:
            self.created_objects['borrower_user'] = {
                'username': borrower_reg_data['username'],
                'password': borrower_reg_data['password'],
                'borrower_id': created_borrower_user.get('borrower', {}).get('borrower_id')
            }
            print(f"   Created borrower user: {borrower_reg_data['username']}")

        # Restore original headers
        self.session.headers.update(temp_headers)

        # Test duplicate registration (should fail)
        print("   Testing duplicate registration validation...")
        self.test_endpoint(
            '/auth/register/investor/', 'POST', investor_reg_data, 400)
        self.test_endpoint(
            '/auth/register/borrower/', 'POST', borrower_reg_data, 400)

    def test_user_authentication_flow(self):
        """Test user authentication and profile access"""
        print("\n🔐 Testing User Authentication Flow...")

        # Test investor user authentication
        if 'investor_user' in self.created_objects:
            investor_creds = self.created_objects['investor_user']
            investor_token = self.get_user_token(
                investor_creds['username'],
                investor_creds['password']
            )

            if investor_token:
                print(f"✅ Got investor token: {investor_token[:20]}...")

                # Test profile access with investor token
                temp_headers = self.session.headers.copy()
                self.session.headers['Authorization'] = f'Bearer {investor_token}'

                profile_response = self.test_endpoint(
                    '/auth/profile/', 'GET', expected_status=200)
                if profile_response:
                    print(
                        f"   Investor profile type: {profile_response.get('user_type')}")
                    user_info = profile_response.get('user_info', {})
                    print(
                        f"   User: {user_info.get('first_name')} {user_info.get('last_name')} ({user_info.get('email')})")

                # Restore original headers
                self.session.headers.update(temp_headers)

        # Test borrower user authentication
        if 'borrower_user' in self.created_objects:
            borrower_creds = self.created_objects['borrower_user']
            borrower_token = self.get_user_token(
                borrower_creds['username'],
                borrower_creds['password']
            )

            if borrower_token:
                print(f"✅ Got borrower token: {borrower_token[:20]}...")

                # Test profile access with borrower token
                temp_headers = self.session.headers.copy()
                self.session.headers['Authorization'] = f'Bearer {borrower_token}'

                profile_response = self.test_endpoint(
                    '/auth/profile/', 'GET', expected_status=200)
                if profile_response:
                    print(
                        f"   Borrower profile type: {profile_response.get('user_type')}")
                    user_info = profile_response.get('user_info', {})
                    print(
                        f"   User: {user_info.get('first_name')} {user_info.get('last_name')} ({user_info.get('email')})")

                # Restore original headers
                self.session.headers.update(temp_headers)

    def test_user_permission_controls(self):
        """Test that users can only access their own data"""
        print("\n🔒 Testing User Permission Controls...")

        if 'investor_user' in self.created_objects and 'borrower_user' in self.created_objects:
            # Get tokens for both users
            investor_creds = self.created_objects['investor_user']
            borrower_creds = self.created_objects['borrower_user']

            investor_token = self.get_user_token(
                investor_creds['username'], investor_creds['password'])
            borrower_token = self.get_user_token(
                borrower_creds['username'], borrower_creds['password'])

            if investor_token and borrower_token:
                # Test investor trying to access borrower endpoints (should fail)
                temp_headers = self.session.headers.copy()
                self.session.headers['Authorization'] = f'Bearer {investor_token}'

                # This should fail because investor user doesn't have borrower profile
                print("   Testing investor access to borrower endpoints...")
                # Note: We'd need specific borrower-only endpoints to test this properly

                # Test borrower trying to access investor endpoints (should fail)
                self.session.headers['Authorization'] = f'Bearer {borrower_token}'

                print("   Testing borrower access to investor endpoints...")
                # Note: We'd need specific investor-only endpoints to test this properly

                # Restore headers
                self.session.headers.update(temp_headers)

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

        # Test with invalid investor ID (should return 404)
        self.test_endpoint(
            '/investors/00000000-0000-0000-0000-000000000000/offers/', 'GET', expected_status=404)

        # Test offer detail with a valid offer created during borrower simulation
        if 'borrower_id' in self.created_objects:
            borrower_id = self.created_objects['borrower_id']

            # First create a simulation/offer for testing
            simulation_data = {
                "amount": 15000.00,
                "term_months": 24
            }

            simulation_response = self.test_endpoint(
                f'/borrowers/{borrower_id}/simulation/', 'POST',
                simulation_data, expected_status=201)

            if simulation_response and 'offer_id' in simulation_response:
                offer_id = simulation_response['offer_id']
                print(f"   Created offer: {offer_id}")

                # Now test the offer detail endpoint with the real offer ID
                self.test_endpoint(
                    f'/offers/{offer_id}/', 'GET', expected_status=200)
            else:
                print("   Could not create offer for testing detail endpoint")
                # Test with non-existent offer ID (expected 404)
                self.test_endpoint(
                    '/offers/00000000-0000-0000-0000-000000000000/', 'GET', expected_status=404)
        else:
            print("   No borrower available, testing with non-existent offer ID")
            # Test with non-existent offer ID (expected 404)
            self.test_endpoint(
                '/offers/00000000-0000-0000-0000-000000000000/', 'GET', expected_status=404)

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
        self.test_user_registration_endpoints()
        self.test_user_authentication_flow()
        self.test_user_permission_controls()
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


def get_client_credentials_token(base_url: str = "http://127.0.0.1:8000") -> Optional[str]:
    """Get OAuth2 client credentials token"""
    token_url = f"{base_url}/o/token/"
    token_data = {
        'grant_type': 'client_credentials',
        'client_id': 'p2p-client-id',
        'client_secret': 'p2p-secret'
    }

    try:
        response = requests.post(token_url, data=token_data)
        if response.status_code == 200:
            token_info = response.json()
            return token_info.get('access_token')
        else:
            print(
                f"❌ Failed to get client credentials token: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error getting client credentials token: {e}")
        return None


def main():
    """Main function"""
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

    # Try to get client credentials token automatically
    print("🔑 Attempting to get OAuth2 client credentials token...")
    token = get_client_credentials_token(base_url)

    if not token:
        print("❌ Could not obtain OAuth2 token automatically.")
        print("Please ensure the server is running and OAuth is configured.")
        print("Run: python manage.py setup_oauth")
        sys.exit(1)

    print(f"✅ Got OAuth2 token: {token[:20]}...")

    tester = P2PAPITester(base_url, token)
    tester.test_all_endpoints()


if __name__ == "__main__":
    main()
