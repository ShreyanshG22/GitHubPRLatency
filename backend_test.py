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

    def test_parse_diff_unauthorized(self):
        """Test parse-diff endpoint without authentication"""
        # Clear session cookies
        self.session.cookies.clear()
        
        test_diff = """diff --git a/test.py b/test.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/test.py
@@ -0,0 +1,3 @@
+def hello():
+    print("Hello World")
+    return True"""
        
        success, response = self.run_test(
            "Parse Diff Unauthorized", "POST", "parse-diff", 401, 
            {"diff_text": test_diff}
        )
        return success

    def test_parse_diff_empty(self):
        """Test parse-diff with empty diff"""
        success, response = self.run_test(
            "Parse Empty Diff", "POST", "parse-diff", 200,
            {"diff_text": ""}
        )
        
        if success:
            expected = {"file_count": 0, "total_blocks": 0, "files": []}
            if (response.get("file_count") == 0 and 
                response.get("total_blocks") == 0 and 
                response.get("files") == []):
                self.log("   ✅ Empty diff correctly parsed")
                return True, response
            else:
                self.log(f"   ❌ Unexpected response: {response}")
        return False, {}

    def test_parse_diff_python_file(self):
        """Test parse-diff with Python file"""
        python_diff = """diff --git a/calculator.py b/calculator.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/calculator.py
@@ -0,0 +1,8 @@
+def add(a, b):
+    return a + b
+
+def multiply(a, b):
+    result = a * b
+    return result
+
+print("Calculator module loaded")"""
        
        success, response = self.run_test(
            "Parse Python Diff", "POST", "parse-diff", 200,
            {"diff_text": python_diff}
        )
        
        if success:
            # Validate response structure
            if (response.get("file_count") == 1 and 
                response.get("total_blocks") == 1 and
                len(response.get("files", [])) == 1):
                
                file_data = response["files"][0]
                if (file_data.get("path") == "calculator.py" and
                    file_data.get("language") == "python" and
                    len(file_data.get("blocks", [])) == 1):
                    
                    block = file_data["blocks"][0]
                    if (block.get("change_type") == "added" and
                        block.get("start_line") == 1 and
                        block.get("end_line") == 8 and
                        block.get("line_count") == 8):
                        
                        self.log("   ✅ Python file correctly parsed")
                        self.log(f"   Language: {file_data['language']}")
                        self.log(f"   Lines: {block['start_line']}-{block['end_line']}")
                        return True, response
            
            self.log(f"   ❌ Unexpected response structure: {response}")
        return False, {}

    def test_parse_diff_cpp_file(self):
        """Test parse-diff with C++ file"""
        cpp_diff = """diff --git a/math_utils.hpp b/math_utils.hpp
new file mode 100644
index 0000000..abcdef1
--- /dev/null
+++ b/math_utils.hpp
@@ -0,0 +1,6 @@
+#ifndef MATH_UTILS_HPP
+#define MATH_UTILS_HPP
+
+int factorial(int n);
+
+#endif"""
        
        success, response = self.run_test(
            "Parse C++ Header Diff", "POST", "parse-diff", 200,
            {"diff_text": cpp_diff}
        )
        
        if success:
            if (response.get("file_count") == 1 and 
                len(response.get("files", [])) == 1):
                
                file_data = response["files"][0]
                if (file_data.get("path") == "math_utils.hpp" and
                    file_data.get("language") == "cpp"):
                    
                    self.log("   ✅ C++ header file correctly parsed")
                    self.log(f"   Language: {file_data['language']}")
                    return True, response
            
            self.log(f"   ❌ Unexpected response: {response}")
        return False, {}

    def test_parse_diff_unknown_file(self):
        """Test parse-diff with unknown file type"""
        unknown_diff = """diff --git a/README.md b/README.md
new file mode 100644
index 0000000..xyz789
--- /dev/null
+++ b/README.md
@@ -0,0 +1,3 @@
+# Project Title
+
+This is a test project."""
        
        success, response = self.run_test(
            "Parse Unknown File Diff", "POST", "parse-diff", 200,
            {"diff_text": unknown_diff}
        )
        
        if success:
            if (response.get("file_count") == 1 and 
                len(response.get("files", [])) == 1):
                
                file_data = response["files"][0]
                if (file_data.get("path") == "README.md" and
                    file_data.get("language") == "unknown"):
                    
                    self.log("   ✅ Unknown file type correctly detected")
                    self.log(f"   Language: {file_data['language']}")
                    return True, response
            
            self.log(f"   ❌ Unexpected response: {response}")
        return False, {}

    def test_parse_diff_modified_lines(self):
        """Test parse-diff with modified lines (additions near removals)"""
        modified_diff = """diff --git a/config.py b/config.py
index 1234567..abcdefg 100644
--- a/config.py
+++ b/config.py
@@ -1,5 +1,6 @@
 import os
 
-DEBUG = False
+DEBUG = True
+VERBOSE = True
 
 DATABASE_URL = os.environ.get('DB_URL')"""
        
        success, response = self.run_test(
            "Parse Modified Lines Diff", "POST", "parse-diff", 200,
            {"diff_text": modified_diff}
        )
        
        if success:
            if (response.get("file_count") == 1 and 
                len(response.get("files", [])) == 1):
                
                file_data = response["files"][0]
                if (file_data.get("path") == "config.py" and
                    file_data.get("language") == "python" and
                    len(file_data.get("blocks", [])) == 1):
                    
                    block = file_data["blocks"][0]
                    if block.get("change_type") == "modified":
                        self.log("   ✅ Modified lines correctly detected")
                        self.log(f"   Change type: {block['change_type']}")
                        return True, response
            
            self.log(f"   ❌ Unexpected response: {response}")
        return False, {}

    def test_parse_diff_multi_file(self):
        """Test parse-diff with multiple files"""
        multi_diff = """diff --git a/main.py b/main.py
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/main.py
@@ -0,0 +1,2 @@
+def main():
+    pass
diff --git a/utils.cpp b/utils.cpp
new file mode 100644
index 0000000..2222222
--- /dev/null
+++ b/utils.cpp
@@ -0,0 +1,3 @@
+#include <iostream>
+
+void hello() {}
diff --git a/config.json b/config.json
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/config.json
@@ -0,0 +1,3 @@
+{
+  "version": "1.0"
+}"""
        
        success, response = self.run_test(
            "Parse Multi-File Diff", "POST", "parse-diff", 200,
            {"diff_text": multi_diff}
        )
        
        if success:
            if (response.get("file_count") == 3 and 
                response.get("total_blocks") == 3 and
                len(response.get("files", [])) == 3):
                
                files = response["files"]
                languages = [f.get("language") for f in files]
                paths = [f.get("path") for f in files]
                
                expected_langs = ["python", "cpp", "unknown"]
                expected_paths = ["main.py", "utils.cpp", "config.json"]
                
                if (set(languages) == set(expected_langs) and 
                    set(paths) == set(expected_paths)):
                    
                    self.log("   ✅ Multi-file diff correctly parsed")
                    self.log(f"   Files: {len(files)}, Blocks: {response['total_blocks']}")
                    self.log(f"   Languages detected: {languages}")
                    return True, response
            
            self.log(f"   ❌ Unexpected response: {response}")
        return False, {}

    def test_parse_diff_line_numbers(self):
        """Test parse-diff line number accuracy"""
        line_diff = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -10,6 +10,8 @@ def existing_function():
     return "existing"
 
 def new_function():
+    # This is a new comment
+    value = 42
     return "new"
 
 # End of file"""
        
        success, response = self.run_test(
            "Parse Line Numbers Diff", "POST", "parse-diff", 200,
            {"diff_text": line_diff}
        )
        
        if success:
            if (response.get("file_count") == 1 and 
                len(response.get("files", [])) == 1):
                
                file_data = response["files"][0]
                if len(file_data.get("blocks", [])) == 1:
                    block = file_data["blocks"][0]
                    # The hunk starts at line 10, and we have 2 added lines
                    # They should be at lines 13-14 based on the context
                    if (block.get("start_line") == 13 and
                        block.get("end_line") == 14 and
                        block.get("line_count") == 2):
                        
                        self.log("   ✅ Line numbers correctly calculated")
                        self.log(f"   Lines: {block['start_line']}-{block['end_line']}")
                        return True, response
            
            self.log(f"   ❌ Unexpected line numbers: {response}")
        return False, {}

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
        
        # Diff Parser Tests (require authentication)
        ("Parse Diff - Empty", tester.test_parse_diff_empty),
        ("Parse Diff - Python File", tester.test_parse_diff_python_file),
        ("Parse Diff - C++ File", tester.test_parse_diff_cpp_file),
        ("Parse Diff - Unknown File", tester.test_parse_diff_unknown_file),
        ("Parse Diff - Modified Lines", tester.test_parse_diff_modified_lines),
        ("Parse Diff - Multi File", tester.test_parse_diff_multi_file),
        ("Parse Diff - Line Numbers", tester.test_parse_diff_line_numbers),
        
        ("Logout", tester.test_auth_logout),
        ("Unauthorized Access", tester.test_invalid_auth),
        ("Parse Diff Unauthorized", tester.test_parse_diff_unauthorized),
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