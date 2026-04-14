#!/usr/bin/env python3
"""
Backend API Testing for PR Review Bot
Tests all authentication, webhook, and dashboard endpoints
"""

import requests
import json
import sys
from datetime import datetime
import time

class PRReviewBotTester:
    def __init__(self, base_url="https://pr-perf-bot.preview.emergentagent.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
        self.tests_run = 0
        self.tests_passed = 0
        self.user_data = None

    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, cookies=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}" if not endpoint.startswith('http') else endpoint
        
        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = self.session.get(url)
            elif method == 'POST':
                response = self.session.post(url, json=data)
            elif method == 'DELETE':
                response = self.session.delete(url)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json() if response.text else {}
                except:
                    return True, {}
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API", "GET", "", 200)

    def test_auth_register(self):
        """Test user registration"""
        test_user_data = {
            "email": f"test_{int(time.time())}@example.com",
            "password": "TestPass123!",
            "name": "Test User"
        }
        
        success, response = self.run_test(
            "User Registration", "POST", "auth/register", 200, test_user_data
        )
        
        if success and response.get('id'):
            self.log(f"   Registered user: {response.get('email')}")
            return True, response
        return False, {}

    def test_auth_login_admin(self):
        """Test admin login"""
        admin_data = {
            "email": "admin@example.com",
            "password": "admin123"
        }
        
        success, response = self.run_test(
            "Admin Login", "POST", "auth/login", 200, admin_data
        )
        
        if success and response.get('id'):
            self.user_data = response
            self.log(f"   Logged in as: {response.get('email')} (Role: {response.get('role')})")
            return True, response
        return False, {}

    def test_auth_me(self):
        """Test get current user"""
        success, response = self.run_test(
            "Get Current User", "GET", "auth/me", 200
        )
        
        if success and response.get('email'):
            self.log(f"   Current user: {response.get('email')}")
            return True, response
        return False, {}

    def test_auth_logout(self):
        """Test logout"""
        return self.run_test("Logout", "POST", "auth/logout", 200)

    def test_webhook_ping(self):
        """Test GitHub webhook ping event"""
        ping_payload = {
            "zen": "Non-blocking is better than blocking.",
            "hook_id": 12345,
            "hook": {
                "type": "Repository",
                "id": 12345,
                "name": "web",
                "active": True,
                "events": ["push", "pull_request"],
                "config": {
                    "content_type": "json",
                    "insecure_ssl": "0",
                    "url": "http://example.com/webhook"
                }
            },
            "repository": {
                "id": 35129377,
                "name": "public-repo",
                "full_name": "baxterthehacker/public-repo",
                "owner": {
                    "login": "baxterthehacker",
                    "id": 6752317
                }
            }
        }
        
        # Add GitHub headers
        headers = {
            'X-GitHub-Event': 'ping',
            'X-GitHub-Delivery': 'test-delivery-123',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}/api/github-webhook"
        
        try:
            response = requests.post(url, json=ping_payload, headers=headers)
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                self.log("✅ GitHub Webhook Ping - Status: 200")
                try:
                    resp_data = response.json()
                    if resp_data.get('message') == 'pong':
                        self.log("   Received expected 'pong' response")
                        return True, resp_data
                except:
                    pass
            else:
                self.log(f"❌ GitHub Webhook Ping - Expected 200, got {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
                
        except Exception as e:
            self.log(f"❌ GitHub Webhook Ping - Error: {str(e)}")
            
        self.tests_run += 1
        return False, {}

    def test_webhook_pull_request(self):
        """Test GitHub webhook pull request event"""
        pr_payload = {
            "action": "opened",
            "number": 1,
            "pull_request": {
                "id": 1,
                "number": 1,
                "title": "Test PR for performance review",
                "user": {
                    "login": "testuser",
                    "id": 123
                },
                "head": {
                    "sha": "abc123def456"
                },
                "html_url": "https://github.com/test/repo/pull/1"
            },
            "repository": {
                "id": 35129377,
                "name": "test-repo",
                "full_name": "testuser/test-repo",
                "owner": {
                    "login": "testuser",
                    "id": 123
                }
            }
        }
        
        headers = {
            'X-GitHub-Event': 'pull_request',
            'X-GitHub-Delivery': 'test-pr-delivery-456',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}/api/github-webhook"
        
        try:
            response = requests.post(url, json=pr_payload, headers=headers)
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                self.log("✅ GitHub Webhook PR Event - Status: 200")
                try:
                    resp_data = response.json()
                    if "Processing PR" in resp_data.get('message', ''):
                        self.log("   PR processing initiated")
                        return True, resp_data
                except:
                    pass
            else:
                self.log(f"❌ GitHub Webhook PR Event - Expected 200, got {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
                
        except Exception as e:
            self.log(f"❌ GitHub Webhook PR Event - Error: {str(e)}")
            
        self.tests_run += 1
        return False, {}

    def test_dashboard_endpoints(self):
        """Test dashboard API endpoints (requires authentication)"""
        endpoints = [
            ("Webhook Logs", "webhook-logs"),
            ("Reviews", "reviews"),
            ("Stats", "stats")
        ]
        
        results = []
        for name, endpoint in endpoints:
            success, response = self.run_test(f"Dashboard {name}", "GET", endpoint, 200)
            results.append((name, success, response))
            
        return results

    def test_invalid_auth(self):
        """Test endpoints without authentication"""
        # Clear session cookies
        self.session.cookies.clear()
        
        success, response = self.run_test(
            "Unauthorized Access", "GET", "stats", 401
        )
        return success

def main():
    print("=" * 60)
    print("🚀 PR Review Bot API Testing")
    print("=" * 60)
    
    tester = PRReviewBotTester()
    
    # Test sequence
    tests = [
        ("Root API", tester.test_root_endpoint),
        ("User Registration", tester.test_auth_register),
        ("Admin Login", tester.test_auth_login_admin),
        ("Current User", tester.test_auth_me),
        ("GitHub Webhook Ping", tester.test_webhook_ping),
        ("GitHub Webhook PR", tester.test_webhook_pull_request),
        ("Dashboard Endpoints", tester.test_dashboard_endpoints),
        ("Logout", tester.test_auth_logout),
        ("Unauthorized Access", tester.test_invalid_auth),
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if test_name == "Dashboard Endpoints":
                # Special handling for multiple endpoint tests
                for endpoint_name, success, response in result:
                    if success:
                        tester.log(f"   ✅ {endpoint_name} endpoint working")
                    else:
                        tester.log(f"   ❌ {endpoint_name} endpoint failed")
        except Exception as e:
            tester.log(f"❌ {test_name} failed with exception: {str(e)}")
        
        print()  # Add spacing between tests
    
    # Final results
    print("=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"📈 Success Rate: {success_rate:.1f}%")
    print("=" * 60)
    
    # Return appropriate exit code
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())