#!/usr/bin/env python3
"""
Test script to validate CPF functionality
"""

from consign_app.api.serializers import validate_cpf
import django
import sys
import os
sys.path.append('/Users/ddp/Documents/Source/ConsignP2P-QITech')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'consign_app.settings')
django.setup()


def test_cpf_validation():
    """Test CPF validation with various cases"""

    print("🧪 Testing CPF Validation Function\n")

    # Test cases: (cpf, expected_result, description)
    test_cases = [
        # Valid CPFs
        ("11144477735", True, "Valid CPF - numbers only"),
        ("111.444.777-35", True, "Valid CPF - with formatting"),
        ("12345678909", True, "Valid CPF - classic test CPF"),
        ("123.456.789-09", True, "Valid CPF - classic test CPF with formatting"),

        # Invalid CPFs
        ("11111111111", False, "Invalid CPF - all same digits"),
        ("12345678900", False, "Invalid CPF - wrong check digits"),
        ("111.444.777-36", False, "Invalid CPF - wrong last digit"),
        ("1234567890", False, "Invalid CPF - only 10 digits"),
        ("123456789012", False, "Invalid CPF - 12 digits"),
        ("", False, "Invalid CPF - empty string"),
        ("abc.def.ghi-jk", False, "Invalid CPF - letters"),
    ]

    passed = 0
    failed = 0

    for cpf, expected, description in test_cases:
        result = validate_cpf(cpf)
        status = "✅ PASS" if result == expected else "❌ FAIL"

        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} | {description}")
        print(f"      CPF: {cpf} | Expected: {expected} | Got: {result}")
        print()

    print(f"📊 Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! CPF validation is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the validation logic.")


if __name__ == "__main__":
    test_cpf_validation()
