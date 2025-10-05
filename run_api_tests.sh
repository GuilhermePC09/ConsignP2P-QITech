#!/bin/bash

# P2P Platform API Testing Suite
# Runs comprehensive tests on all API endpoints

set -e  # Exit on any error

echo "🚀 P2P Platform API Testing Suite"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="http://127.0.0.1:8000"
OAUTH_TOKEN="${OAUTH_TOKEN:-F5Qra0pZsI8ev3tlMTa8nx1uOdlDKG}"
PYTHON_CMD="/Users/ddp/Documents/Source/ConsignP2P-QITech/venv/bin/python"
# Default client credentials (can be overridden via env vars)
CLIENT_ID="${CLIENT_ID:-p2p-client-id}"
CLIENT_SECRET="${CLIENT_SECRET:-my-plain-secret-123}"

echo -e "${BLUE}Configuration:${NC}"
echo "Base URL: $BASE_URL"
echo "OAuth Token: $OAUTH_TOKEN"
echo ""

## Check if server is running. Do NOT attempt to start the server inside this script.
echo -e "${YELLOW}Checking if Django server is running...${NC}"

# Ensure PYTHON_CMD exists, otherwise fall back to `python`
if [ ! -x "$PYTHON_CMD" ]; then
    echo -e "${YELLOW}Warning: configured PYTHON_CMD ($PYTHON_CMD) not executable, falling back to 'python' in PATH${NC}"
    PYTHON_CMD="$(command -v python || command -v python3 || true)"
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${RED}ERROR: No Python interpreter found. Activate your virtualenv or set PYTHON_CMD.${NC}"
        exit 1
    fi
fi

# Check server reachability. Accept any HTTP response code as "server responding"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/test/" -H "Authorization: Bearer $OAUTH_TOKEN" || echo "000")
if [ "$HTTP_CODE" = "000" ]; then
    echo -e "${RED}❌ Server is not running or not accessible${NC}"
    echo "Please start the Django server in another terminal with:"
    echo "  $PYTHON_CMD manage.py runserver"
    exit 1
else
    echo -e "${GREEN}✅ Server is reachable (HTTP $HTTP_CODE)${NC}"
fi

echo ""

# Run Django unit tests using manage.py (ensures Django settings are configured)
echo -e "${BLUE}Running Django Unit Tests...${NC}"
echo "================================"
$PYTHON_CMD manage.py test consign_app.api.tests --verbosity=2

echo ""

# Run integration tests
echo -e "${BLUE}Running Integration Tests...${NC}"
echo "============================"
$PYTHON_CMD test_api_endpoints.py "$OAUTH_TOKEN" "$BASE_URL"

echo ""

# Test with curl for basic connectivity
echo -e "${BLUE}Running Basic Connectivity Tests...${NC}"
echo "==================================="

# Test auth endpoint
echo -n "Testing auth endpoint... "
if curl -s -f "$BASE_URL/api/v1/test/" -H "Authorization: Bearer $OAUTH_TOKEN" > /dev/null; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL${NC}"
fi

# Test investor creation
echo -n "Testing investor creation... "
RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null \
    -X POST "$BASE_URL/api/v1/investors/" \
    -H "Authorization: Bearer $OAUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "type": "pf",
        "name": "Shell Test Investor",
        "document": "99988877766",
        "email": "shell.test@example.com",
        "phone_number": "+5511555555555",
        "suitability_profile": "moderate",
        "preferred_payout_method": "pix"
    }')

if [ "$RESPONSE" = "201" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL (HTTP $RESPONSE)${NC}"
fi

# Test borrower creation
echo -n "Testing borrower creation... "
RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null \
    -X POST "$BASE_URL/api/v1/borrowers/" \
    -H "Authorization: Bearer $OAUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Shell Test Borrower",
        "document": "11100099988",
        "email": "shell.borrower@example.com",
        "phone_number": "+5511444444444",
        "consigned_margin": "2500.00"
    }')

if [ "$RESPONSE" = "201" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL (HTTP $RESPONSE)${NC}"
fi

echo ""

# Performance test
echo -e "${BLUE}Running Performance Tests...${NC}"
echo "============================"

echo -n "Testing response time for auth endpoint... "
RESPONSE_TIME=$(curl -w "%{time_total}" -s -o /dev/null \
    "$BASE_URL/api/v1/test/" \
    -H "Authorization: Bearer $OAUTH_TOKEN")

if (( $(echo "$RESPONSE_TIME < 1.0" | bc -l) )); then
    echo -e "${GREEN}✅ ${RESPONSE_TIME}s (GOOD)${NC}"
elif (( $(echo "$RESPONSE_TIME < 3.0" | bc -l) )); then
    echo -e "${YELLOW}⚠️  ${RESPONSE_TIME}s (SLOW)${NC}"
else
    echo -e "${RED}❌ ${RESPONSE_TIME}s (TOO SLOW)${NC}"
fi

echo ""

# Security tests
echo -e "${BLUE}Running Security Tests...${NC}"
echo "========================="

# Test without authentication
echo -n "Testing endpoint without auth... "
RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/api/v1/test/")
if [ "$RESPONSE" = "401" ]; then
    echo -e "${GREEN}✅ PASS (401 Unauthorized)${NC}"
else
    echo -e "${RED}❌ FAIL (Expected 401, got $RESPONSE)${NC}"
fi

# Test with invalid token
echo -n "Testing with invalid token... "
RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null \
    "$BASE_URL/api/v1/test/" \
    -H "Authorization: Bearer invalid_token_123")
if [ "$RESPONSE" = "401" ]; then
    echo -e "${GREEN}✅ PASS (401 Unauthorized)${NC}"
else
    echo -e "${RED}❌ FAIL (Expected 401, got $RESPONSE)${NC}"
fi

echo ""
echo -e "${GREEN}🎉 API Testing Complete!${NC}"
echo ""
echo "📊 Check the following files for detailed results:"
echo "   - api_test_results.json (Integration test results)"
echo "   - Django test output above (Unit test results)"
echo ""
echo "💡 To run individual test suites:"
echo "   Django tests: python manage.py test"
echo "   Integration tests: python test_api_endpoints.py $OAUTH_TOKEN"
echo ""