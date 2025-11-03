#!/bin/bash
# Test the CDF STT service
# Usage: ./test_stt.sh HOST PORT

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 HOST PORT"
    echo
    echo "Example:"
    echo "  $0 ssh6.vast.ai 12345"
    echo "  $0 localhost 8000"
    echo
    echo "Get HOST and PORT from:"
    echo "  - Vast.ai console: https://vast.ai/console/instances/"
    echo "  - Or run: ./get_connection_info.sh"
    exit 1
fi

HOST="$1"
PORT="$2"
BASE_URL="http://${HOST}:${PORT}"

echo "=========================================="
echo "CDF STT Service Test Suite"
echo "=========================================="
echo "Testing: $BASE_URL"
echo

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

test_passed=0
test_failed=0

run_test() {
    local test_name="$1"
    local test_command="$2"

    echo -n "Testing $test_name... "

    if eval "$test_command" > /tmp/test_output.txt 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        test_passed=$((test_passed + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        test_failed=$((test_failed + 1))
        cat /tmp/test_output.txt
        return 1
    fi
}

# Test 1: Connection
echo "1. Connection Tests"
echo "-------------------"
run_test "Basic connectivity" "curl -s --connect-timeout 5 --max-time 10 '${BASE_URL}/' > /dev/null"

if [ $? -eq 0 ]; then
    # Test 2: Root endpoint
    run_test "Root endpoint" "curl -s '${BASE_URL}/' | jq -e '.service' > /dev/null"

    # Test 3: Health check
    echo
    echo "2. Health Check"
    echo "---------------"
    if run_test "Health endpoint" "curl -s '${BASE_URL}/health' | jq -e '.status == \"healthy\"' > /dev/null"; then
        echo
        echo "Health details:"
        curl -s "${BASE_URL}/health" | jq .
    fi

    # Test 4: Languages
    echo
    echo "3. Language Support"
    echo "-------------------"
    if run_test "Languages endpoint" "curl -s '${BASE_URL}/languages' | jq -e '.count' > /dev/null"; then
        LANG_COUNT=$(curl -s "${BASE_URL}/languages" | jq -r '.count')
        echo "Supported languages: $LANG_COUNT"
    fi

    # Test 5: Metrics
    echo
    echo "4. Metrics"
    echo "----------"
    run_test "Metrics endpoint" "curl -s '${BASE_URL}/metrics' | grep -q 'transcriptions_total'"

    # Test 6: Transcription (if test file exists)
    echo
    echo "5. Transcription Test"
    echo "---------------------"

    TEST_FILE="../test_samples/test.wav"
    if [ ! -f "$TEST_FILE" ]; then
        TEST_FILE="test.wav"
    fi

    if [ -f "$TEST_FILE" ]; then
        if run_test "Transcribe audio file" "curl -s -X POST '${BASE_URL}/transcribe' -F 'file=@${TEST_FILE}' | jq -e '.text' > /dev/null"; then
            echo
            echo "Transcription result:"
            RESULT=$(curl -s -X POST "${BASE_URL}/transcribe" -F "file=@${TEST_FILE}")
            echo "$RESULT" | jq '{text, language, duration, processing_time}'

            # Calculate processing metrics
            DURATION=$(echo "$RESULT" | jq -r '.duration')
            PROC_TIME=$(echo "$RESULT" | jq -r '.processing_time')

            if [ "$DURATION" != "null" ] && [ "$PROC_TIME" != "null" ]; then
                SPEED=$(echo "scale=2; $PROC_TIME / $DURATION" | bc)
                echo
                echo "Performance:"
                echo "  Audio duration: ${DURATION}s"
                echo "  Processing time: ${PROC_TIME}s"
                echo "  Speed: ${SPEED}x realtime"
            fi
        fi
    else
        echo -e "${YELLOW}⚠ SKIP${NC} - No test audio file found"
        echo "Create test.wav to test transcription"
        echo
        echo "Quick test file creation:"
        echo "  # Using sox (if available):"
        echo "  sox -n -r 16000 -c 1 test.wav synth 3 sine 440"
        echo
        echo "  # Or download a sample:"
        echo "  wget https://www2.cs.uic.edu/~i101/SoundFiles/BabyElephantWalk60.wav -O test.wav"
    fi
else
    echo -e "${RED}Cannot connect to service${NC}"
    echo
    echo "Troubleshooting:"
    echo "1. Check if the service is running:"
    echo "   - Visit: https://vast.ai/console/instances/"
    echo "   - Verify instance status is 'running'"
    echo
    echo "2. Verify port forwarding:"
    echo "   - Check the port mapping for 8000 in Vast.ai console"
    echo "   - Make sure you're using the forwarded port"
    echo
    echo "3. Check instance logs:"
    echo "   - Click 'Logs' button in Vast.ai console"
    echo "   - Look for 'Uvicorn running on http://0.0.0.0:8000'"
    echo
    echo "4. Try SSH tunnel:"
    echo "   ssh -p SSH_PORT -L 8000:localhost:8000 root@SSH_HOST"
    echo "   Then test: ./test_stt.sh localhost 8000"
fi

# Summary
echo
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "Passed: ${GREEN}${test_passed}${NC}"
echo -e "Failed: ${RED}${test_failed}${NC}"
echo

if [ $test_failed -eq 0 ] && [ $test_passed -gt 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo
    echo "API Documentation: ${BASE_URL}/docs"
    echo "Metrics: ${BASE_URL}/metrics"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
