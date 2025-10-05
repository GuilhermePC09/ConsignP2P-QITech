#!/usr/bin/env python3
"""
Test script to test borrower registration with CPF validation
"""

import requests
import json


def test_borrower_registration():
    """Test borrower registration endpoint"""

    print("🧪 Testing Borrower Registration with CPF\n")

    # Test data with a valid CPF
    test_data = {
        'user_type': 'borrower',
        'first_name': 'João',
        'last_name': 'Silva',
        'email': 'joao.teste@example.com',
        'phone': '(11) 99999-9999',
        'document': '111.444.777-35',  # Valid test CPF
        'password': 'senha123456',
        'employment_status': 'employed',
        'monthly_income': '5000.00'
    }

    # URL for registration
    url = 'http://localhost:8000/api/v1/auth-test/register/'

    try:
        # Get the page first to get CSRF token
        session = requests.Session()
        response = session.get(url)

        if response.status_code == 200:
            print("✅ Successfully accessed registration page")

            # Extract CSRF token from response
            csrf_token = None
            if 'csrftoken' in session.cookies:
                csrf_token = session.cookies['csrftoken']
                print(f"✅ Got CSRF token: {csrf_token[:10]}...")

            if csrf_token:
                # Add CSRF token to headers
                headers = {
                    'X-CSRFToken': csrf_token,
                    'Referer': url
                }
                test_data['csrfmiddlewaretoken'] = csrf_token

                # Submit registration
                response = session.post(url, data=test_data, headers=headers)

                print(f"\n📤 Submitted registration form")
                print(f"📥 Response status: {response.status_code}")

                if response.status_code == 200:
                    if 'sucesso' in response.text.lower():
                        print("🎉 Registration successful!")
                    elif 'erro' in response.text.lower() or 'error' in response.text.lower():
                        print("❌ Registration failed - check error messages")
                        # Try to extract error messages
                        if 'CPF' in response.text:
                            print("⚠️  CPF-related error found in response")
                    else:
                        print(
                            "ℹ️  Registration form submitted, check response manually")
                elif response.status_code == 302:
                    print("🎉 Registration successful! (Redirected)")
                else:
                    print(f"❌ Unexpected response: {response.status_code}")

            else:
                print("❌ Could not get CSRF token")
        else:
            print(
                f"❌ Could not access registration page: {response.status_code}")

    except requests.ConnectionError:
        print("❌ Could not connect to server. Make sure Django server is running on localhost:8000")
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")


if __name__ == "__main__":
    test_borrower_registration()
