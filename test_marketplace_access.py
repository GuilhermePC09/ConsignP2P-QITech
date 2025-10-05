#!/usr/bin/env python3
"""
Test script to verify marketplace access restrictions for borrowers vs investors
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


def test_marketplace_access():
    """Test marketplace access restrictions"""
    client = Client()

    # Create test users
    borrower_user = User.objects.create_user(
        username='test_borrower_marketplace',
        email='test_borrower_marketplace@test.com',
        password='testpass123'
    )

    investor_user = User.objects.create_user(
        username='test_investor_marketplace',
        email='test_investor_marketplace@test.com',
        password='testpass123'
    )

    # Create borrower profile
    borrower = Borrower.objects.create(
        name='Test Borrower',
        document='12345678901',
        email='test_borrower_marketplace@test.com',
        monthly_income=5000.00,
        user=borrower_user
    )

    # Create investor profile
    investor = Investor.objects.create(
        type='pf',
        name='Test Investor',
        document='98765432101',
        email='test_investor_marketplace@test.com',
        user=investor_user
    )

    print("✅ Test users and profiles created")

    # Test 1: Borrower trying to access marketplace
    print("\n🔍 Test 1: Borrower accessing marketplace")
    client.login(username='test_borrower_marketplace', password='testpass123')
    response = client.get(reverse('frontend:marketplace'))

    if response.status_code == 302:  # Redirect
        print(f"✅ Borrower correctly redirected to: {response.url}")
        print(f"   Status code: {response.status_code}")
    else:
        print(f"❌ Borrower was not redirected. Status: {response.status_code}")

    client.logout()

    # Test 2: Investor accessing marketplace
    print("\n🔍 Test 2: Investor accessing marketplace")
    client.login(username='test_investor_marketplace', password='testpass123')
    response = client.get(reverse('frontend:marketplace'))

    if response.status_code == 200:  # Success
        print(f"✅ Investor can access marketplace")
        print(f"   Status code: {response.status_code}")
        print(
            f"   Page title contains: {'Ofertas Disponíveis' if 'Ofertas Disponíveis' in response.content.decode() else 'Unknown content'}")
    else:
        print(
            f"❌ Investor cannot access marketplace. Status: {response.status_code}")

    client.logout()

    # Test 3: Anonymous user accessing marketplace
    print("\n🔍 Test 3: Anonymous user accessing marketplace")
    response = client.get(reverse('frontend:marketplace'))

    if response.status_code == 302:  # Should redirect to login
        print(f"✅ Anonymous user redirected to login")
        print(f"   Status code: {response.status_code}")
    else:
        print(
            f"❌ Anonymous user was not redirected. Status: {response.status_code}")

    # Test 4: Check home page buttons for borrower
    print("\n🔍 Test 4: Home page buttons for borrower")
    client.login(username='test_borrower_marketplace', password='testpass123')
    response = client.get(reverse('frontend:home'))

    if response.status_code == 200:
        content = response.content.decode()
        if 'Ver Ofertas' not in content:
            print("✅ Home page correctly hides 'Ver Ofertas' button for borrowers")
        else:
            print("❌ Home page still shows 'Ver Ofertas' button for borrowers")

    client.logout()

    # Test 5: Check home page buttons for investor
    print("\n🔍 Test 5: Home page buttons for investor")
    client.login(username='test_investor_marketplace', password='testpass123')
    response = client.get(reverse('frontend:home'))

    if response.status_code == 200:
        content = response.content.decode()
        if 'Ver Ofertas' in content:
            print("✅ Home page correctly shows 'Ver Ofertas' button for investors")
        else:
            print("❌ Home page hides 'Ver Ofertas' button for investors")

    client.logout()

    # Cleanup
    borrower_user.delete()
    investor_user.delete()
    print("\n🧹 Test cleanup completed")


if __name__ == '__main__':
    print("🚀 Testing marketplace access restrictions...")
    test_marketplace_access()
    print("\n✨ All tests completed!")
