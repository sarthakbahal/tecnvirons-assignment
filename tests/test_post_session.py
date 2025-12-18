"""
Test script for Post-Session Processing
Run this after starting the server to verify all functionality
"""

import requests
import time
import json

BASE_URL = "http://localhost:8001"

def test_health_check():
    """Test 1: Health Check"""
    print("\n🔍 Test 1: Health Check")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✅ Health check passed")

def test_list_sessions():
    """Test 2: List Sessions"""
    print("\n📋 Test 2: List Sessions")
    response = requests.get(f"{BASE_URL}/api/sessions")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Total sessions: {data.get('count', 0)}")
    if data.get('sessions'):
        print(f"Latest session: {data['sessions'][0]['session_id'][:8]}...")
    print("✅ List sessions passed")
    return data.get('sessions', [])

def test_session_summary(session_id):
    """Test 3: Get Session Summary"""
    print(f"\n📊 Test 3: Get Session Summary for {session_id[:8]}...")
    response = requests.get(f"{BASE_URL}/api/session/{session_id}/summary")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Summary: {data.get('summary', 'N/A')[:100]}...")
        print(f"Status: {data.get('status')}")
        print(f"Topics: {data.get('topics', [])}")
        print(f"Sentiment: {data.get('sentiment')}")
        print("✅ Session summary passed")
    else:
        print(f"⚠️ Session summary returned: {response.json()}")

def test_regenerate_summary(session_id):
    """Test 4: Regenerate Summary"""
    print(f"\n🔄 Test 4: Regenerate Summary for {session_id[:8]}...")
    response = requests.post(f"{BASE_URL}/api/session/{session_id}/regenerate-summary")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            print(f"New summary: {data['summary'].get('summary', 'N/A')[:100]}...")
            print("✅ Regenerate summary passed")
        else:
            print(f"⚠️ Regeneration failed: {data}")
    else:
        print(f"⚠️ Request failed: {response.json()}")

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("🚀 Starting Post-Session Processing Tests")
    print("=" * 60)
    
    try:
        # Test 1: Health Check
        test_health_check()
        
        # Test 2: List Sessions
        sessions = test_list_sessions()
        
        # Test 3 & 4: If we have sessions, test their summaries
        if sessions:
            test_session = sessions[0]
            session_id = test_session['session_id']
            
            test_session_summary(session_id)
            
            # Only regenerate if session is completed
            if test_session.get('status') == 'completed':
                test_regenerate_summary(session_id)
        else:
            print("\n⚠️ No sessions found. Create a chat session first!")
            print("   1. Open http://localhost:8000")
            print("   2. Send some messages")
            print("   3. Close the browser tab")
            print("   4. Wait a few seconds")
            print("   5. Run this test again")
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Cannot connect to server")
        print("   Make sure the server is running:")
        print("   uvicorn proj:app --reload --port 8000")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")

if __name__ == "__main__":
    run_all_tests()
