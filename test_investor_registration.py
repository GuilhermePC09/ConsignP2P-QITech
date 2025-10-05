#!/usr/bin/env python3
"""
Test script to verify investor registration functionality
"""

from consign_app.core_db.models import Borrower, Investor
import os
import sys
import django
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'consign_app.settings')
sys.path.insert(0, os.path.abspath('.'))
django.setup()


def test_investor_registration():
    """Test investor registration flow"""
    client = Client()

    print("🚀 Testing investor registration system...")

    # Test 1: Check registration choice page loads
    print("\n🔍 Test 1: Registration choice page")
    response = client.get(reverse('frontend:register_choice'))
    if response.status_code == 200:
        print("✅ Registration choice page loads correctly")
        content = response.content.decode()
        if 'Quero Investir' in content and 'Quero Pedir Empréstimo' in content:
            print("✅ Both registration options are displayed")
        else:
            print("❌ Registration options not found in page")
    else:
        print(f"❌ Registration choice page failed: {response.status_code}")

    # Test 2: Check borrower registration page loads
    print("\n🔍 Test 2: Borrower registration page")
    response = client.get(reverse('frontend:register'))
    if response.status_code == 200:
        print("✅ Borrower registration page loads correctly")
        content = response.content.decode()
        if 'Cadastro de Solicitante' in content:
            print("✅ Borrower-specific content is displayed")
        else:
            print("⚠️  Borrower-specific content not found")
    else:
        print(f"❌ Borrower registration page failed: {response.status_code}")

    # Test 3: Check investor registration page loads
    print("\n🔍 Test 3: Investor registration page")
    response = client.get(reverse('frontend:register_investor'))
    if response.status_code == 200:
        print("✅ Investor registration page loads correctly")
        content = response.content.decode()
        if 'Cadastro de Investidor' in content:
            print("✅ Investor-specific content is displayed")
        else:
            print("⚠️  Investor-specific content not found")
        if 'Tipo de Pessoa' in content:
            print("✅ Investor-specific form fields are present")
        else:
            print("❌ Investor-specific form fields missing")
    else:
        print(f"❌ Investor registration page failed: {response.status_code}")

    # Test 4: Test investor registration form submission
    print("\n🔍 Test 4: Investor registration form submission")

    # Clean up any existing test data
    User.objects.filter(email='test_investor_reg@test.com').delete()

    investor_data = {
        'user_type': 'pf',
        'first_name': 'Test',
        'last_name': 'Investor',
        'document': '98765432100',  # Valid CPF format
        'email': 'test_investor_reg@test.com',
        'phone_number': '(11) 99999-9999',
        'password1': 'testpass123',
        'password2': 'testpass123'
    }

    response = client.post(
        reverse('frontend:register_investor'), data=investor_data, follow=True)

    if response.status_code == 200:
        # Check if user was created
        if User.objects.filter(email='test_investor_reg@test.com').exists():
            print("✅ Investor user account created successfully")

            # Check if investor profile was created
            if Investor.objects.filter(email='test_investor_reg@test.com').exists():
                print("✅ Investor profile created successfully")
                investor = Investor.objects.get(
                    email='test_investor_reg@test.com')
                print(f"   - Name: {investor.name}")
                print(f"   - Type: {investor.type}")
                print(f"   - Document: {investor.document}")
            else:
                print("❌ Investor profile not created")
        else:
            print("❌ Investor user account not created")
            print(f"   Response URL: {response.wsgi_request.path}")
    else:
        print(f"❌ Investor registration failed: {response.status_code}")

    # Cleanup
    User.objects.filter(email='test_investor_reg@test.com').delete()

    print("\n✨ Investor registration testing completed!")


if __name__ == '__main__':
    test_investor_registration()
