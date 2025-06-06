#!/bin/bash

# Test runner script for Bug #001 fix
# Author: Drew (Developer)
# Date: 2025-06-05

echo "🧪 Running Bug #001 Fix Verification"
echo "===================================="
echo "Bug: Fake Job Data Generation"
echo "Developer: Drew"
echo "Date: 2025-06-05"
echo ""

# Check if we're in the right directory
if [ ! -f "main_orchestrator.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Run unit tests
echo "🔬 Running Unit Tests..."
echo "------------------------"
python3 test_bug_001_fix.py
unit_test_result=$?

echo ""
echo "🔍 Running Manual Verification..."
echo "----------------------------------"
python3 test_manual_verification.py
manual_test_result=$?

echo ""
echo "📊 Test Summary"
echo "==============="

if [ $unit_test_result -eq 0 ] && [ $manual_test_result -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED!"
    echo "✅ Bug #001 fix has been verified"
    echo "✅ Ready for code review and QA testing"
    echo ""
    echo "📋 Acceptance Criteria Met:"
    echo "✅ Remove all hardcoded fake job data"
    echo "✅ Remove sample job insertion"
    echo "✅ Add validation to ensure no fake URLs"
    echo "✅ System fails gracefully when no real jobs found"
    echo ""
    echo "🎯 Next Steps:"
    echo "1. Submit for code review"
    echo "2. QA testing with real API"
    echo "3. Deploy to staging environment"
    exit 0
else
    echo "❌ SOME TESTS FAILED!"
    echo "❌ Bug #001 fix needs additional work"
    
    if [ $unit_test_result -ne 0 ]; then
        echo "❌ Unit tests failed"
    fi
    
    if [ $manual_test_result -ne 0 ]; then
        echo "❌ Manual verification failed"
    fi
    
    echo ""
    echo "🔧 Required Actions:"
    echo "1. Review failed tests above"
    echo "2. Fix any remaining issues"
    echo "3. Re-run tests until all pass"
    exit 1
fi

