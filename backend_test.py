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
    def __init__(self, base_url="https://253e16ce-73d8-4a78-81f3-a4f8b6e6507a.preview.emergentagent.com"):
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
            elif method == 'PUT':
                response = self.session.put(url, json=data)
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

    # ─── C++ Analyzer Tests ──────────────────────────────────────────────

    def test_cpp_analyzer_unauthorized(self):
        """Test C++ analyzer without authentication"""
        # Clear session cookies
        self.session.cookies.clear()
        
        test_code = "int add(int a, int b) { return a + b; }"
        
        success, response = self.run_test(
            "C++ Analyzer Unauthorized", "POST", "analyze-cpp", 401,
            {"code": test_code}
        )
        return success, response

    def test_cpp_analyzer_clean_code(self):
        """Test C++ analyzer with clean code (should return 0 findings)"""
        clean_code = "int add(int a, int b) { return a + b; }"
        
        success, response = self.run_test(
            "C++ Analyzer Clean Code", "POST", "analyze-cpp", 200,
            {"code": clean_code, "file_path": "clean.cpp", "start_line": 1}
        )
        
        if success:
            if (response.get("total_findings") == 0 and
                response.get("high") == 0 and
                response.get("medium") == 0 and
                response.get("low") == 0 and
                response.get("findings") == []):
                
                self.log("   ✅ Clean code correctly returns 0 findings")
                return True, response
            else:
                self.log(f"   ❌ Expected 0 findings, got: {response}")
        return False, {}

    def test_cpp_analyzer_pass_by_value(self):
        """Test pass-by-value detection (high severity)"""
        code_with_issue = """void process_data(std::vector<int> data) {
    data.push_back(42);
}"""
        
        success, response = self.run_test(
            "C++ Pass By Value", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("high") >= 1 and
                len(findings) >= 1 and
                any(f.get("rule") == "pass_by_value" and f.get("severity") == "high" 
                    for f in findings)):
                
                self.log("   ✅ Pass-by-value correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Pass-by-value not detected: {response}")
        return False, {}

    def test_cpp_analyzer_vector_no_reserve(self):
        """Test vector push_back without reserve (high severity)"""
        code_with_issue = """void fill_vector() {
    std::vector<int> vec;
    for (int i = 0; i < 1000; ++i) {
        vec.push_back(i);
    }
}"""
        
        success, response = self.run_test(
            "C++ Vector No Reserve", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("high") >= 1 and
                any(f.get("rule") == "vector_no_reserve" and f.get("severity") == "high"
                    for f in findings)):
                
                self.log("   ✅ Vector no reserve correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Vector no reserve not detected: {response}")
        return False, {}

    def test_cpp_analyzer_map_over_unordered(self):
        """Test std::map usage (medium severity)"""
        code_with_issue = "std::map<int, std::string> lookup_table;"
        
        success, response = self.run_test(
            "C++ Map Over Unordered", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("medium") >= 1 and
                any(f.get("rule") == "map_over_unordered_map" and f.get("severity") == "medium"
                    for f in findings)):
                
                self.log("   ✅ Map over unordered_map correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Map over unordered_map not detected: {response}")
        return False, {}

    def test_cpp_analyzer_heap_alloc_in_loop(self):
        """Test heap allocation in loop (high severity)"""
        code_with_issue = """void allocate_in_loop() {
    for (int i = 0; i < 100; ++i) {
        auto ptr = std::make_shared<int>(i);
    }
}"""
        
        success, response = self.run_test(
            "C++ Heap Alloc In Loop", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("high") >= 1 and
                any(f.get("rule") == "heap_alloc_in_loop" and f.get("severity") == "high"
                    for f in findings)):
                
                self.log("   ✅ Heap allocation in loop correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Heap allocation in loop not detected: {response}")
        return False, {}

    def test_cpp_analyzer_unnecessary_copy(self):
        """Test unnecessary container copy (medium severity)"""
        code_with_issue = """void copy_container() {
    std::vector<int> original = {1, 2, 3};
    std::vector<int> copy = original;
}"""
        
        success, response = self.run_test(
            "C++ Unnecessary Copy", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("medium") >= 1 and
                any(f.get("rule") == "unnecessary_copy" and f.get("severity") == "medium"
                    for f in findings)):
                
                self.log("   ✅ Unnecessary copy correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Unnecessary copy not detected: {response}")
        return False, {}

    def test_cpp_analyzer_large_stack_alloc(self):
        """Test large stack allocation (medium severity)"""
        code_with_issue = "char buffer[8192];"
        
        success, response = self.run_test(
            "C++ Large Stack Alloc", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("medium") >= 1 and
                any(f.get("rule") == "large_stack_alloc" and f.get("severity") == "medium"
                    for f in findings)):
                
                self.log("   ✅ Large stack allocation correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Large stack allocation not detected: {response}")
        return False, {}

    def test_cpp_analyzer_mutex_in_loop(self):
        """Test mutex in tight loop (high severity)"""
        code_with_issue = """void lock_in_loop() {
    for (int i = 0; i < 1000; ++i) {
        std::lock_guard<std::mutex> lock(mtx);
        data[i] = i;
    }
}"""
        
        success, response = self.run_test(
            "C++ Mutex In Loop", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("high") >= 1 and
                any(f.get("rule") == "mutex_in_tight_loop" and f.get("severity") == "high"
                    for f in findings)):
                
                self.log("   ✅ Mutex in tight loop correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Mutex in tight loop not detected: {response}")
        return False, {}

    def test_cpp_analyzer_string_concat_in_loop(self):
        """Test string concatenation in loop (medium severity)"""
        code_with_issue = """void concat_in_loop() {
    std::string result;
    for (int i = 0; i < 100; ++i) {
        result += "data";
    }
}"""
        
        success, response = self.run_test(
            "C++ String Concat In Loop", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("medium") >= 1 and
                any(f.get("rule") == "string_concat_in_loop" and f.get("severity") == "medium"
                    for f in findings)):
                
                self.log("   ✅ String concatenation in loop correctly detected")
                return True, response
            else:
                self.log(f"   ❌ String concatenation in loop not detected: {response}")
        return False, {}

    def test_cpp_analyzer_shared_ptr_overhead(self):
        """Test shared_ptr overhead (low severity)"""
        code_with_issue = "std::shared_ptr<int> ptr = std::make_shared<int>(42);"
        
        success, response = self.run_test(
            "C++ Shared Ptr Overhead", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("low") >= 1 and
                any(f.get("rule") == "shared_ptr_overhead" and f.get("severity") == "low"
                    for f in findings)):
                
                self.log("   ✅ Shared_ptr overhead correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Shared_ptr overhead not detected: {response}")
        return False, {}

    def test_cpp_analyzer_exception_in_loop(self):
        """Test try/catch in loop (medium severity)"""
        code_with_issue = """void exception_in_loop() {
    for (int i = 0; i < 100; ++i) {
        try {
            risky_operation(i);
        } catch (...) {
            handle_error();
        }
    }
}"""
        
        success, response = self.run_test(
            "C++ Exception In Loop", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("medium") >= 1 and
                any(f.get("rule") == "exception_in_loop" and f.get("severity") == "medium"
                    for f in findings)):
                
                self.log("   ✅ Exception in loop correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Exception in loop not detected: {response}")
        return False, {}

    def test_cpp_analyzer_virtual_dispatch(self):
        """Test virtual function dispatch (low severity)"""
        code_with_issue = "virtual void process() = 0;"
        
        success, response = self.run_test(
            "C++ Virtual Dispatch", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("low") >= 1 and
                any(f.get("rule") == "virtual_dispatch" and f.get("severity") == "low"
                    for f in findings)):
                
                self.log("   ✅ Virtual dispatch correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Virtual dispatch not detected: {response}")
        return False, {}

    def test_cpp_analyzer_endl_flush(self):
        """Test std::endl usage (low severity)"""
        code_with_issue = 'std::cout << "Hello" << std::endl;'
        
        success, response = self.run_test(
            "C++ Endl Flush", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("low") >= 1 and
                any(f.get("rule") == "endl_flush" and f.get("severity") == "low"
                    for f in findings)):
                
                self.log("   ✅ Endl flush correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Endl flush not detected: {response}")
        return False, {}

    def test_cpp_analyzer_inefficient_find(self):
        """Test std::find usage (medium severity)"""
        code_with_issue = "auto it = std::find(container.begin(), container.end(), value);"
        
        success, response = self.run_test(
            "C++ Inefficient Find", "POST", "analyze-cpp", 200,
            {"code": code_with_issue}
        )
        
        if success:
            findings = response.get("findings", [])
            if (response.get("medium") >= 1 and
                any(f.get("rule") == "inefficient_find" and f.get("severity") == "medium"
                    for f in findings)):
                
                self.log("   ✅ Inefficient find correctly detected")
                return True, response
            else:
                self.log(f"   ❌ Inefficient find not detected: {response}")
        return False, {}

    def test_cpp_analyzer_findings_structure(self):
        """Test that findings have all required fields and are sorted by line"""
        code_with_multiple_issues = """std::string process(std::string data) {  // line 1: pass_by_value
    std::map<int, int> lookup;              // line 2: map_over_unordered_map
    std::shared_ptr<int> ptr;               // line 3: shared_ptr_overhead
    return data;
}"""
        
        success, response = self.run_test(
            "C++ Findings Structure", "POST", "analyze-cpp", 200,
            {"code": code_with_multiple_issues}
        )
        
        if success:
            findings = response.get("findings", [])
            if len(findings) >= 3:
                # Check all findings have required fields
                required_fields = ["line", "severity", "rule", "explanation", "suggestion", "snippet"]
                all_have_fields = all(
                    all(field in finding for field in required_fields)
                    for finding in findings
                )
                
                # Check findings are sorted by line number
                lines = [f.get("line", 0) for f in findings]
                is_sorted = lines == sorted(lines)
                
                if all_have_fields and is_sorted:
                    self.log("   ✅ Findings have all required fields and are sorted by line")
                    self.log(f"   Found {len(findings)} issues on lines: {lines}")
                    return True, response
                else:
                    self.log(f"   ❌ Missing fields or not sorted. Fields check: {all_have_fields}, Sorted: {is_sorted}")
            else:
                self.log(f"   ❌ Expected at least 3 findings, got {len(findings)}")
        return False, {}

    # ─── Comment Formatting Tests ───────────────────────────────────────

    def test_preview_comment_static_findings(self):
        """Test preview-comment with static analysis findings"""
        static_findings = [
            {
                "path": "src/main.cpp",
                "line": 42,
                "severity": "high",
                "rule": "pass_by_value",
                "explanation": "std::vector passed by value triggers a deep copy on every call",
                "suggestion": "Pass by const reference: const std::vector<int>& data",
                "snippet": "void process(std::vector<int> data) {"
            },
            {
                "path": "src/utils.cpp", 
                "line": 15,
                "severity": "medium",
                "rule": "map_over_unordered_map",
                "explanation": "std::map uses O(log n) lookup, unordered_map gives O(1)",
                "suggestion": "Use std::unordered_map unless you need sorted iteration"
            }
        ]
        
        success, response = self.run_test(
            "Preview Comment - Static Findings",
            "POST",
            "preview-comment",
            200,
            {
                "comments": static_findings,
                "summary": "Found 2 performance issues in C++ code",
                "score": 65
            }
        )
        
        if success and "markdown" in response:
            markdown = response["markdown"]
            # Check for severity headers
            if "⛔ Performance Error" in markdown and "⚠️ Performance Warning" in markdown:
                self.log("   ✅ Severity headers found in markdown")
            else:
                self.log("   ❌ Missing severity headers in markdown")
                return False, {}
                
            # Check for rule names
            if "**Rule:** `pass_by_value`" in markdown and "**Rule:** `map_over_unordered_map`" in markdown:
                self.log("   ✅ Rule names found in markdown")
            else:
                self.log("   ❌ Missing rule names in markdown")
                return False, {}
                
            # Check for code snippet
            if "```cpp" in markdown and "void process(std::vector<int> data)" in markdown:
                self.log("   ✅ Code snippet found in markdown")
            else:
                self.log("   ❌ Missing code snippet in markdown")
                return False, {}
                
        return success, response

    def test_preview_comment_empty_list(self):
        """Test preview-comment with empty comments list"""
        success, response = self.run_test(
            "Preview Comment - Empty List",
            "POST", 
            "preview-comment",
            200,
            {
                "comments": [],
                "summary": "No issues found",
                "score": 100
            }
        )
        
        if success and "markdown" in response:
            markdown = response["markdown"]
            if "No issues found. Code looks good! :white_check_mark:" in markdown:
                self.log("   ✅ Empty list message found")
            else:
                self.log("   ❌ Missing empty list message")
                return False, {}
                
        return success, response

    def test_preview_comment_llm_style(self):
        """Test preview-comment with LLM-style comments (body field only)"""
        llm_comments = [
            {
                "path": "src/algorithm.cpp",
                "line": 23,
                "severity": "medium",
                "body": "This nested loop has O(n²) complexity which could be optimized"
            }
        ]
        
        success, response = self.run_test(
            "Preview Comment - LLM Style",
            "POST",
            "preview-comment", 
            200,
            {
                "comments": llm_comments,
                "summary": "Algorithm complexity analysis",
                "score": 70
            }
        )
        
        if success and "markdown" in response:
            markdown = response["markdown"]
            if "This nested loop has O(n²) complexity" in markdown:
                self.log("   ✅ LLM comment body found in explanation section")
            else:
                self.log("   ❌ Missing LLM comment in markdown")
                return False, {}
                
        return success, response

    def test_preview_comment_mixed_severities(self):
        """Test preview-comment with mixed severities to check sorting"""
        mixed_comments = [
            {
                "path": "test.cpp",
                "line": 30,
                "severity": "low", 
                "rule": "suggestion_rule",
                "explanation": "Low priority suggestion",
                "suggestion": "Consider this improvement"
            },
            {
                "path": "test.cpp", 
                "line": 10,
                "severity": "high",
                "rule": "error_rule", 
                "explanation": "Critical performance issue",
                "suggestion": "Fix this immediately"
            },
            {
                "path": "test.cpp",
                "line": 20,
                "severity": "medium",
                "rule": "warning_rule",
                "explanation": "Moderate performance concern", 
                "suggestion": "Should be addressed"
            }
        ]
        
        success, response = self.run_test(
            "Preview Comment - Mixed Severities",
            "POST",
            "preview-comment",
            200,
            {
                "comments": mixed_comments,
                "summary": "Mixed severity analysis",
                "score": 60
            }
        )
        
        if success and "markdown" in response:
            markdown = response["markdown"]
            # Check that high severity appears before medium and low
            high_pos = markdown.find("Critical performance issue")
            med_pos = markdown.find("Moderate performance concern")
            low_pos = markdown.find("Low priority suggestion")
            
            if high_pos < med_pos < low_pos:
                self.log("   ✅ Comments sorted by severity (high -> medium -> low)")
            else:
                self.log("   ❌ Comments not properly sorted by severity")
                return False, {}
                
        return success, response

    def test_preview_comment_score_bar(self):
        """Test that score bar visualization is included"""
        success, response = self.run_test(
            "Preview Comment - Score Bar",
            "POST",
            "preview-comment",
            200,
            {
                "comments": [],
                "summary": "Score bar test",
                "score": 75
            }
        )
        
        if success and "markdown" in response:
            markdown = response["markdown"]
            if "**75/100**" in markdown and "█" in markdown:
                self.log("   ✅ Score bar with filled blocks found")
            else:
                self.log("   ❌ Missing score bar visualization")
                return False, {}
                
        return success, response

    def test_preview_comment_stats_line(self):
        """Test that stats line counting errors/warnings/suggestions is included"""
        comments_with_stats = [
            {"severity": "high", "rule": "error1", "explanation": "Error 1", "suggestion": "Fix 1"},
            {"severity": "high", "rule": "error2", "explanation": "Error 2", "suggestion": "Fix 2"},
            {"severity": "medium", "rule": "warn1", "explanation": "Warning 1", "suggestion": "Fix 3"},
            {"severity": "low", "rule": "info1", "explanation": "Info 1", "suggestion": "Fix 4"}
        ]
        
        success, response = self.run_test(
            "Preview Comment - Stats Line",
            "POST",
            "preview-comment",
            200,
            {
                "comments": comments_with_stats,
                "summary": "Stats line test",
                "score": 50
            }
        )
        
        if success and "markdown" in response:
            markdown = response["markdown"]
            if "⛔ 2 error(s)" in markdown and "⚠️ 1 warning(s)" in markdown and "💡 1 suggestion(s)" in markdown:
                self.log("   ✅ Stats line with correct counts found")
            else:
                self.log("   ❌ Missing or incorrect stats line")
                return False, {}
                
        return success, response

    def test_preview_comment_merged_format(self):
        """Test preview-comment with merged format '[rule] explanation — suggestion'"""
        merged_comments = [
            {
                "path": "src/parser.cpp",
                "line": 55,
                "severity": "medium",
                "body": "[inefficient_algorithm] This algorithm runs in O(n²) time — Consider using a hash table for O(n) lookup"
            }
        ]
        
        success, response = self.run_test(
            "Preview Comment - Merged Format",
            "POST",
            "preview-comment",
            200,
            {
                "comments": merged_comments,
                "summary": "Merged format test",
                "score": 80
            }
        )
        
        if success and "markdown" in response:
            markdown = response["markdown"]
            if "**Rule:** `inefficient_algorithm`" in markdown and "This algorithm runs in O(n²) time" in markdown and "Consider using a hash table" in markdown:
                self.log("   ✅ Merged format correctly parsed into separate sections")
            else:
                self.log("   ❌ Merged format not properly parsed")
                return False, {}
                
        return success, response

    def test_preview_comment_auth_required(self):
        """Test that preview-comment requires authentication"""
        # Create new session without login
        temp_session = requests.Session()
        temp_session.headers.update({'Content-Type': 'application/json'})
        url = f"{self.base_url}/api/preview-comment"
        
        self.tests_run += 1
        self.log(f"🔍 Testing Preview Comment - Auth Required...")
        
        try:
            response = temp_session.post(url, json={
                "comments": [],
                "summary": "Test",
                "score": 100
            })
            
            if response.status_code == 401:
                self.tests_passed += 1
                self.log("   ✅ 401 Unauthorized without authentication")
                return True, {}
            else:
                self.log(f"   ❌ Expected 401, got {response.status_code}")
                return False, {}
                
        except Exception as e:
            self.log(f"   ❌ Error: {str(e)}")
            return False, {}

    def test_analyze_cpp_integration(self):
        """Test full pipeline: analyze-cpp -> preview-comment"""
        cpp_code = """
void process(std::vector<int> data) {
    std::map<int, std::string> cache;
    for (int i = 0; i < data.size(); i++) {
        cache[i] = std::to_string(data[i]);
    }
}
"""
        
        # First get C++ analysis
        success, cpp_response = self.run_test(
            "C++ Analysis for Integration",
            "POST",
            "analyze-cpp",
            200,
            {
                "code": cpp_code,
                "file_path": "test.cpp",
                "start_line": 1
            }
        )
        
        if not success:
            return False, {}
            
        # Convert findings to comment format
        findings = cpp_response.get("findings", [])
        comments = []
        for finding in findings:
            comments.append({
                "path": "test.cpp",
                "line": finding["line"],
                "severity": finding["severity"],
                "rule": finding["rule"],
                "explanation": finding["explanation"],
                "suggestion": finding["suggestion"],
                "snippet": finding.get("snippet", "")
            })
        
        # Test preview with those findings
        success, preview_response = self.run_test(
            "Preview with C++ Findings",
            "POST",
            "preview-comment",
            200,
            {
                "comments": comments,
                "summary": "C++ static analysis complete",
                "score": 60
            }
        )
        
        if success and "markdown" in preview_response:
            markdown = preview_response["markdown"]
            if "pass_by_value" in markdown or "map_over_unordered_map" in markdown:
                self.log("   ✅ C++ findings successfully formatted in preview")
            else:
                self.log("   ❌ C++ findings not found in preview markdown")
                return False, {}
                
        return success, preview_response

    # ─── P1 Feature Tests ────────────────────────────────────────────────

    def test_webhook_deduplication(self):
        """Test webhook deduplication using same X-GitHub-Delivery header"""
        delivery_id = f"test-dedup-{int(time.time())}"
        
        ping_payload = {
            "zen": "Deduplication test",
            "hook_id": 12345,
            "repository": {
                "id": 35129377,
                "name": "test-repo",
                "full_name": "testuser/test-repo",
                "owner": {"login": "testuser", "id": 123}
            }
        }
        
        headers = {
            'X-GitHub-Event': 'ping',
            'X-GitHub-Delivery': delivery_id,
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}/api/github-webhook"
        
        # First request should succeed
        self.tests_run += 1
        self.log(f"🔍 Testing Webhook Deduplication - First Request...")
        
        try:
            response1 = requests.post(url, json=ping_payload, headers=headers)
            if response1.status_code == 200:
                self.tests_passed += 1
                self.log("   ✅ First request succeeded")
                
                # Second request with same delivery_id should return duplicate
                self.tests_run += 1
                self.log(f"🔍 Testing Webhook Deduplication - Second Request...")
                
                response2 = requests.post(url, json=ping_payload, headers=headers)
                if response2.status_code == 200:
                    try:
                        resp_data = response2.json()
                        if resp_data.get('duplicate') is True:
                            self.tests_passed += 1
                            self.log("   ✅ Second request correctly returned duplicate: true")
                            return True, resp_data
                        else:
                            self.log(f"   ❌ Expected duplicate: true, got: {resp_data}")
                    except:
                        self.log("   ❌ Failed to parse response JSON")
                else:
                    self.log(f"   ❌ Second request failed with status {response2.status_code}")
            else:
                self.log(f"   ❌ First request failed with status {response1.status_code}")
                
        except Exception as e:
            self.log(f"   ❌ Error: {str(e)}")
            
        return False, {}

    def test_webhook_rate_limiting(self):
        """Test webhook rate limiting by sending rapid requests"""
        repo_name = f"testuser/rate-limit-test-{int(time.time())}"
        
        ping_payload = {
            "zen": "Rate limit test",
            "hook_id": 12345,
            "repository": {
                "id": 35129377,
                "name": "rate-limit-test",
                "full_name": repo_name,
                "owner": {"login": "testuser", "id": 123}
            }
        }
        
        url = f"{self.base_url}/api/github-webhook"
        
        self.tests_run += 1
        self.log(f"🔍 Testing Webhook Rate Limiting...")
        
        try:
            # Send many rapid requests (default limit is 30 per minute)
            rate_limited = False
            for i in range(35):  # Send more than the limit
                headers = {
                    'X-GitHub-Event': 'ping',
                    'X-GitHub-Delivery': f'rate-test-{i}-{int(time.time())}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(url, json=ping_payload, headers=headers)
                
                if response.status_code == 429:
                    rate_limited = True
                    self.tests_passed += 1
                    self.log(f"   ✅ Rate limit triggered after {i+1} requests (429 status)")
                    return True, {"rate_limited_after": i+1}
                elif response.status_code != 200:
                    self.log(f"   ❌ Unexpected status {response.status_code} on request {i+1}")
                    return False, {}
                    
                # Small delay to avoid overwhelming the server
                time.sleep(0.1)
            
            if not rate_limited:
                self.log("   ❌ Rate limit not triggered after 35 requests")
                return False, {}
                
        except Exception as e:
            self.log(f"   ❌ Error: {str(e)}")
            return False, {}

    def test_repo_settings_disabled_analysis(self):
        """Test webhook with repo settings enabled=false"""
        # First create a repo setting with enabled=false
        repo_name = f"testuser/disabled-repo-{int(time.time())}"
        
        # Create repo settings with enabled=false
        success, _ = self.run_test(
            "Create Disabled Repo Settings",
            "POST",
            "repo-settings",
            200,
            {
                "repo_full_name": repo_name,
                "enabled": False,
                "auto_post_comments": True,
                "rate_limit_rpm": 30
            }
        )
        
        if not success:
            return False, {}
        
        # Now send webhook for this repo
        pr_payload = {
            "action": "opened",
            "number": 1,
            "pull_request": {
                "id": 1,
                "number": 1,
                "title": "Test PR for disabled repo",
                "user": {"login": "testuser", "id": 123},
                "head": {"sha": "abc123def456"},
                "html_url": f"https://github.com/{repo_name}/pull/1"
            },
            "repository": {
                "id": 35129377,
                "name": repo_name.split('/')[1],
                "full_name": repo_name,
                "owner": {"login": "testuser", "id": 123}
            }
        }
        
        headers = {
            'X-GitHub-Event': 'pull_request',
            'X-GitHub-Delivery': f'disabled-test-{int(time.time())}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}/api/github-webhook"
        
        self.tests_run += 1
        self.log(f"🔍 Testing Disabled Repo Analysis...")
        
        try:
            response = requests.post(url, json=pr_payload, headers=headers)
            if response.status_code == 200:
                try:
                    resp_data = response.json()
                    if "Analysis disabled" in resp_data.get('message', ''):
                        self.tests_passed += 1
                        self.log("   ✅ Disabled repo correctly returned 'Analysis disabled' message")
                        return True, resp_data
                    else:
                        self.log(f"   ❌ Expected 'Analysis disabled' message, got: {resp_data}")
                except:
                    self.log("   ❌ Failed to parse response JSON")
            else:
                self.log(f"   ❌ Expected 200, got {response.status_code}")
                
        except Exception as e:
            self.log(f"   ❌ Error: {str(e)}")
            
        return False, {}

    def test_available_rules(self):
        """Test GET /api/available-rules returns all 14 C++ rule names"""
        success, response = self.run_test(
            "Available Rules", "GET", "available-rules", 200
        )
        
        if success:
            rules = response.get("rules", [])
            expected_rules = [
                "pass_by_value", "vector_no_reserve", "map_over_unordered_map",
                "heap_alloc_in_loop", "unnecessary_copy", "large_stack_alloc",
                "mutex_in_tight_loop", "string_concat_in_loop", "shared_ptr_overhead",
                "exception_in_loop", "virtual_dispatch", "endl_flush",
                "inefficient_find", "move_on_return"
            ]
            
            if len(rules) == 14 and all(rule in rules for rule in expected_rules):
                self.log(f"   ✅ All 14 C++ rules returned: {len(rules)} rules")
                return True, response
            else:
                self.log(f"   ❌ Expected 14 rules, got {len(rules)}: {rules}")
                missing = [r for r in expected_rules if r not in rules]
                if missing:
                    self.log(f"   Missing rules: {missing}")
        
        return False, {}

    def test_repo_settings_crud(self):
        """Test full CRUD operations on repo settings"""
        repo_name = f"testorg/crud-test-{int(time.time())}"
        
        # CREATE - POST /api/repo-settings
        create_data = {
            "repo_full_name": repo_name,
            "enabled": True,
            "auto_post_comments": False,
            "rate_limit_rpm": 60,
            "severity_threshold": "medium",
            "rule_config": {
                "disabled_rules": ["endl_flush"],
                "severity_overrides": {"shared_ptr_overhead": "high"}
            }
        }
        
        success, create_response = self.run_test(
            "Create Repo Settings", "POST", "repo-settings", 200, create_data
        )
        
        if not success:
            return False, {}
        
        # Verify created data
        if (create_response.get("repo_full_name") == repo_name and
            create_response.get("enabled") is True and
            create_response.get("auto_post_comments") is False and
            create_response.get("rate_limit_rpm") == 60):
            self.log("   ✅ Repo settings created with correct data")
        else:
            self.log(f"   ❌ Created data mismatch: {create_response}")
            return False, {}
        
        # READ - GET /api/repo-settings (list all)
        success, list_response = self.run_test(
            "List Repo Settings", "GET", "repo-settings", 200
        )
        
        if success:
            found_repo = any(r.get("repo_full_name") == repo_name for r in list_response)
            if found_repo:
                self.log("   ✅ Created repo found in list")
            else:
                self.log("   ❌ Created repo not found in list")
                return False, {}
        else:
            return False, {}
        
        # READ - GET /api/repo-settings/{owner}/{name} (specific repo)
        owner, name = repo_name.split('/')
        success, get_response = self.run_test(
            "Get Specific Repo Settings", "GET", f"repo-settings/{owner}/{name}", 200
        )
        
        if success:
            if (get_response.get("repo_full_name") == repo_name and
                get_response.get("severity_threshold") == "medium" and
                get_response.get("rule_config", {}).get("disabled_rules") == ["endl_flush"]):
                self.log("   ✅ Specific repo settings retrieved correctly")
            else:
                self.log(f"   ❌ Retrieved data mismatch: {get_response}")
                return False, {}
        else:
            return False, {}
        
        # UPDATE - PUT /api/repo-settings/{owner}/{name} (partial update)
        update_data = {
            "enabled": False,
            "rate_limit_rpm": 120
        }
        
        success, update_response = self.run_test(
            "Update Repo Settings", "PUT", f"repo-settings/{owner}/{name}", 200, update_data
        )
        
        if success:
            if (update_response.get("enabled") is False and
                update_response.get("rate_limit_rpm") == 120 and
                update_response.get("auto_post_comments") is False):  # Should preserve old value
                self.log("   ✅ Repo settings updated correctly (partial update)")
            else:
                self.log(f"   ❌ Updated data mismatch: {update_response}")
                return False, {}
        else:
            return False, {}
        
        # DELETE - DELETE /api/repo-settings/{owner}/{name}
        success, delete_response = self.run_test(
            "Delete Repo Settings", "DELETE", f"repo-settings/{owner}/{name}", 200
        )
        
        if success:
            if "deleted" in delete_response.get("message", "").lower():
                self.log("   ✅ Repo settings deleted successfully")
            else:
                self.log(f"   ❌ Unexpected delete response: {delete_response}")
                return False, {}
        else:
            return False, {}
        
        # Verify deletion - GET should return defaults with is_default=true
        success, default_response = self.run_test(
            "Get Deleted Repo (Should Return Defaults)", "GET", f"repo-settings/{owner}/{name}", 200
        )
        
        if success:
            if (default_response.get("is_default") is True and
                default_response.get("enabled") is True and  # Default values
                default_response.get("rate_limit_rpm") == 30):
                self.log("   ✅ Deleted repo returns defaults with is_default=true")
            else:
                self.log(f"   ❌ Expected defaults, got: {default_response}")
                return False, {}
        else:
            return False, {}
        
        return True, {"crud_operations": "all_passed"}

    def test_repo_settings_edge_cases(self):
        """Test repo settings edge cases"""
        repo_name = f"testorg/edge-case-{int(time.time())}"
        
        # Test creating duplicate repo settings (should return 409)
        create_data = {
            "repo_full_name": repo_name,
            "enabled": True
        }
        
        # First creation should succeed
        success, _ = self.run_test(
            "Create Repo Settings (First)", "POST", "repo-settings", 200, create_data
        )
        
        if not success:
            return False, {}
        
        # Second creation should fail with 409
        success, _ = self.run_test(
            "Create Duplicate Repo Settings", "POST", "repo-settings", 409, create_data
        )
        
        if not success:
            self.log("   ❌ Duplicate creation should return 409")
            return False, {}
        else:
            self.log("   ✅ Duplicate creation correctly returned 409")
        
        # Test deleting non-existent repo (should return 404)
        fake_repo = f"fake/nonexistent-{int(time.time())}"
        owner, name = fake_repo.split('/')
        
        success, _ = self.run_test(
            "Delete Non-existent Repo", "DELETE", f"repo-settings/{owner}/{name}", 404
        )
        
        if not success:
            self.log("   ❌ Deleting non-existent repo should return 404")
            return False, {}
        else:
            self.log("   ✅ Deleting non-existent repo correctly returned 404")
        
        return True, {}

    def test_repo_settings_auth_required(self):
        """Test that all repo settings endpoints require authentication"""
        # Clear session cookies
        temp_session = requests.Session()
        temp_session.headers.update({'Content-Type': 'application/json'})
        
        endpoints = [
            ("GET", "available-rules"),
            ("GET", "repo-settings"),
            ("GET", "repo-settings/test/repo"),
            ("POST", "repo-settings"),
            ("PUT", "repo-settings/test/repo"),
            ("DELETE", "repo-settings/test/repo")
        ]
        
        all_passed = True
        for method, endpoint in endpoints:
            url = f"{self.base_url}/api/{endpoint}"
            
            self.tests_run += 1
            self.log(f"🔍 Testing {method} {endpoint} - Auth Required...")
            
            try:
                if method == "GET":
                    response = temp_session.get(url)
                elif method == "POST":
                    response = temp_session.post(url, json={"repo_full_name": "test/repo"})
                elif method == "PUT":
                    response = temp_session.put(url, json={"enabled": True})
                elif method == "DELETE":
                    response = temp_session.delete(url)
                
                if response.status_code == 401:
                    self.tests_passed += 1
                    self.log(f"   ✅ {method} {endpoint} correctly returned 401")
                else:
                    self.log(f"   ❌ {method} {endpoint} expected 401, got {response.status_code}")
                    all_passed = False
                    
            except Exception as e:
                self.log(f"   ❌ {method} {endpoint} error: {str(e)}")
                all_passed = False
        
        return all_passed, {}

    def test_cpp_analyzer_custom_rules(self):
        """Test C++ analyzer with custom rule configuration"""
        # Test code that triggers multiple rules
        test_code = """
void process(std::vector<int> data) {  // pass_by_value
    std::cout << "Processing" << std::endl;  // endl_flush
    std::shared_ptr<int> ptr;  // shared_ptr_overhead
}
"""
        
        # Test 1: Disabled rules - should NOT produce endl_flush findings
        config_disabled = {
            "disabled_rules": ["endl_flush"]
        }
        
        success, response = self.run_test(
            "C++ Analyzer - Disabled Rules",
            "POST",
            "analyze-cpp",
            200,
            {
                "code": test_code,
                "file_path": "test.cpp",
                "config": config_disabled
            }
        )
        
        if success:
            findings = response.get("findings", [])
            endl_findings = [f for f in findings if f.get("rule") == "endl_flush"]
            if len(endl_findings) == 0:
                self.log("   ✅ Disabled rules correctly excluded endl_flush findings")
            else:
                self.log(f"   ❌ Found {len(endl_findings)} endl_flush findings despite being disabled")
                return False, {}
        else:
            return False, {}
        
        # Test 2: Enabled rules only - should ONLY produce pass_by_value findings
        config_enabled = {
            "enabled_rules": ["pass_by_value"]
        }
        
        success, response = self.run_test(
            "C++ Analyzer - Enabled Rules Only",
            "POST",
            "analyze-cpp",
            200,
            {
                "code": test_code,
                "file_path": "test.cpp",
                "config": config_enabled
            }
        )
        
        if success:
            findings = response.get("findings", [])
            rule_names = [f.get("rule") for f in findings]
            if all(rule == "pass_by_value" for rule in rule_names) and len(findings) > 0:
                self.log(f"   ✅ Enabled rules only produced {len(findings)} pass_by_value findings")
            else:
                self.log(f"   ❌ Expected only pass_by_value findings, got: {rule_names}")
                return False, {}
        else:
            return False, {}
        
        # Test 3: Severity overrides - should change shared_ptr_overhead to high
        config_severity = {
            "severity_overrides": {"shared_ptr_overhead": "high"}
        }
        
        success, response = self.run_test(
            "C++ Analyzer - Severity Overrides",
            "POST",
            "analyze-cpp",
            200,
            {
                "code": test_code,
                "file_path": "test.cpp",
                "config": config_severity
            }
        )
        
        if success:
            findings = response.get("findings", [])
            shared_ptr_findings = [f for f in findings if f.get("rule") == "shared_ptr_overhead"]
            if (len(shared_ptr_findings) > 0 and 
                shared_ptr_findings[0].get("severity") == "high"):
                self.log("   ✅ Severity override correctly changed shared_ptr_overhead to high")
            else:
                self.log(f"   ❌ Severity override failed. Findings: {shared_ptr_findings}")
                return False, {}
        else:
            return False, {}
        
        return True, {"custom_rules_tests": "all_passed"}

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
        
        # C++ Analyzer Tests (require authentication)
        ("C++ Analyzer - Clean Code", tester.test_cpp_analyzer_clean_code),
        ("C++ Analyzer - Pass By Value", tester.test_cpp_analyzer_pass_by_value),
        ("C++ Analyzer - Vector No Reserve", tester.test_cpp_analyzer_vector_no_reserve),
        ("C++ Analyzer - Map Over Unordered", tester.test_cpp_analyzer_map_over_unordered),
        ("C++ Analyzer - Heap Alloc In Loop", tester.test_cpp_analyzer_heap_alloc_in_loop),
        ("C++ Analyzer - Unnecessary Copy", tester.test_cpp_analyzer_unnecessary_copy),
        ("C++ Analyzer - Large Stack Alloc", tester.test_cpp_analyzer_large_stack_alloc),
        ("C++ Analyzer - Mutex In Loop", tester.test_cpp_analyzer_mutex_in_loop),
        ("C++ Analyzer - String Concat In Loop", tester.test_cpp_analyzer_string_concat_in_loop),
        ("C++ Analyzer - Shared Ptr Overhead", tester.test_cpp_analyzer_shared_ptr_overhead),
        ("C++ Analyzer - Exception In Loop", tester.test_cpp_analyzer_exception_in_loop),
        ("C++ Analyzer - Virtual Dispatch", tester.test_cpp_analyzer_virtual_dispatch),
        ("C++ Analyzer - Endl Flush", tester.test_cpp_analyzer_endl_flush),
        ("C++ Analyzer - Inefficient Find", tester.test_cpp_analyzer_inefficient_find),
        ("C++ Analyzer - Findings Structure", tester.test_cpp_analyzer_findings_structure),
        
        # Comment Formatting Tests (require authentication)
        ("Preview Comment - Static Findings", tester.test_preview_comment_static_findings),
        ("Preview Comment - Empty List", tester.test_preview_comment_empty_list),
        ("Preview Comment - LLM Style", tester.test_preview_comment_llm_style),
        ("Preview Comment - Mixed Severities", tester.test_preview_comment_mixed_severities),
        ("Preview Comment - Score Bar", tester.test_preview_comment_score_bar),
        ("Preview Comment - Stats Line", tester.test_preview_comment_stats_line),
        ("Preview Comment - Merged Format", tester.test_preview_comment_merged_format),
        ("Preview Comment - Auth Required", tester.test_preview_comment_auth_required),
        ("C++ Integration Pipeline", tester.test_analyze_cpp_integration),
        
        # P1 Feature Tests (require authentication for some)
        ("P1: Webhook Deduplication", tester.test_webhook_deduplication),
        ("P1: Webhook Rate Limiting", tester.test_webhook_rate_limiting),
        ("P1: Disabled Repo Analysis", tester.test_repo_settings_disabled_analysis),
        ("P1: Available Rules", tester.test_available_rules),
        ("P1: Repo Settings CRUD", tester.test_repo_settings_crud),
        ("P1: Repo Settings Edge Cases", tester.test_repo_settings_edge_cases),
        ("P1: Repo Settings Auth Required", tester.test_repo_settings_auth_required),
        ("P1: C++ Custom Rules Config", tester.test_cpp_analyzer_custom_rules),
        
        ("Logout", tester.test_auth_logout),
        ("Unauthorized Access", tester.test_invalid_auth),
        ("Parse Diff Unauthorized", tester.test_parse_diff_unauthorized),
        ("C++ Analyzer Unauthorized", tester.test_cpp_analyzer_unauthorized),
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