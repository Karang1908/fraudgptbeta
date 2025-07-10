import requests
import unittest
import base64
import os
import sys
from datetime import datetime
import time

# Get the backend URL from the frontend .env file
BACKEND_URL = "https://cd5f201c-4189-4787-b19f-841238b53ae7.preview.emergentagent.com"
API_URL = f"{BACKEND_URL}/api"

class FraudGPTAPITester(unittest.TestCase):
    """Test suite for FraudGPT API endpoints"""
    
    def setUp(self):
        """Setup for each test"""
        self.session_id = None
    
    def test_01_api_root(self):
        """Test the API root endpoint"""
        print("\n🔍 Testing API root endpoint...")
        response = requests.get(f"{API_URL}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.json())
        print("✅ API root endpoint is working")
    
    def test_02_create_session(self):
        """Test creating a new chat session"""
        print("\n🔍 Testing session creation...")
        response = requests.post(f"{API_URL}/chat/sessions")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("id", data)
        self.assertIn("title", data)
        self.assertIn("created_at", data)
        self.assertEqual(data["title"], "New Chat")
        
        # Save session ID for later tests
        self.__class__.session_id = data["id"]
        print(f"✅ Session created with ID: {self.__class__.session_id}")
    
    def test_03_get_sessions(self):
        """Test getting all chat sessions"""
        print("\n🔍 Testing get all sessions...")
        response = requests.get(f"{API_URL}/chat/sessions")
        self.assertEqual(response.status_code, 200)
        sessions = response.json()
        self.assertIsInstance(sessions, list)
        
        # Check if our created session is in the list
        session_ids = [session["id"] for session in sessions]
        self.assertIn(self.__class__.session_id, session_ids)
        print(f"✅ Found {len(sessions)} sessions, including our test session")
    
    def test_04_send_text_message(self):
        """Test sending a text message"""
        print("\n🔍 Testing sending text message...")
        
        # Ensure we have a session ID
        if not hasattr(self.__class__, 'session_id') or not self.__class__.session_id:
            self.test_02_create_session()
        
        message = "Is this email legitimate? 'Dear customer, your account has been compromised. Click here to reset your password.'"
        
        response = requests.post(
            f"{API_URL}/chat/send",
            json={
                "session_id": self.__class__.session_id,
                "message": message,
                "image_base64": None
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("response", data)
        self.assertIn("session_id", data)
        self.assertIn("message_id", data)
        self.assertEqual(data["session_id"], self.__class__.session_id)
        
        # Wait for AI to process
        time.sleep(2)
        print("✅ Text message sent and response received")
    
    def test_05_get_messages(self):
        """Test getting messages for a session"""
        print("\n🔍 Testing get messages for session...")
        
        # Ensure we have a session with messages
        if not hasattr(self.__class__, 'session_id') or not self.__class__.session_id:
            self.test_02_create_session()
            self.test_04_send_text_message()
        
        response = requests.get(f"{API_URL}/chat/sessions/{self.__class__.session_id}/messages")
        self.assertEqual(response.status_code, 200)
        messages = response.json()
        self.assertIsInstance(messages, list)
        self.assertGreaterEqual(len(messages), 2)  # Should have at least user message and AI response
        
        # Check message structure
        for message in messages:
            self.assertIn("id", message)
            self.assertIn("session_id", message)
            self.assertIn("role", message)
            self.assertIn("content", message)
            self.assertIn("timestamp", message)
        
        print(f"✅ Found {len(messages)} messages in the session")
    
    def test_06_delete_session(self):
        """Test deleting a chat session"""
        print("\n🔍 Testing session deletion...")
        
        # Ensure we have a session ID
        if not hasattr(self.__class__, 'session_id') or not self.__class__.session_id:
            self.test_02_create_session()
        
        response = requests.delete(f"{API_URL}/chat/sessions/{self.__class__.session_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("message", data)
        
        # Verify session is deleted
        response = requests.get(f"{API_URL}/chat/sessions")
        sessions = response.json()
        session_ids = [session["id"] for session in sessions]
        self.assertNotIn(self.__class__.session_id, session_ids)
        
        print("✅ Session deleted successfully")

def run_tests():
    """Run all tests"""
    print("\n🔍 Starting FraudGPT API Tests 🔍")
    print(f"Testing against API URL: {API_URL}")
    
    # Create a test suite
    suite = unittest.TestSuite()
    suite.addTest(FraudGPTAPITester('test_01_api_root'))
    suite.addTest(FraudGPTAPITester('test_02_create_session'))
    suite.addTest(FraudGPTAPITester('test_03_get_sessions'))
    suite.addTest(FraudGPTAPITester('test_04_send_text_message'))
    suite.addTest(FraudGPTAPITester('test_05_get_messages'))
    suite.addTest(FraudGPTAPITester('test_06_delete_session'))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n📊 Test Summary:")
    print(f"Ran {result.testsRun} tests")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    return len(result.failures) + len(result.errors)

if __name__ == "__main__":
    sys.exit(run_tests())