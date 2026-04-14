#!/usr/bin/env python3
"""
Test just the P1 features that were failing
"""

import requests
import json
import sys
from datetime import datetime
import time

class P1FeatureTester:
    def __init__(self, base_url="https://253e16ce-73d8-4a78-81f3-a4f8b6e6507a.preview.emergentagent.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
        self.tests_run = 0
        self.tests_passed = 0

    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None):
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
            self.log(f"   Logged in as: {response.get('email')} (Role: {response.get('role')})")
            return True, response
        return False, {}

    def test_repo_settings_crud_update(self):
        """Test just the UPDATE part of repo settings CRUD"""
        repo_name = f"testorg/update-test-{int(time.time())}"
        
        # CREATE first
        create_data = {
            "repo_full_name": repo_name,
            "enabled": True,
            "auto_post_comments": False,
            "rate_limit_rpm": 60
        }
        
        success, _ = self.run_test(
            "Create Repo for Update Test", "POST", "repo-settings", 200, create_data
        )
        
        if not success:
            return False, {}
        
        # UPDATE - PUT /api/repo-settings/{owner}/{name} (partial update)
        owner, name = repo_name.split('/')
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
                return True, update_response
            else:
                self.log(f"   ❌ Updated data mismatch: {update_response}")
                return False, {}
        else:
            return False, {}

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
    print("🚀 Testing P1 Features (Failed Tests)")
    print("=" * 60)
    
    tester = P1FeatureTester()
    
    # Login first
    tester.test_auth_login_admin()
    
    # Test the failing features
    tests = [
        ("P1: Repo Settings UPDATE", tester.test_repo_settings_crud_update),
        ("P1: C++ Custom Rules Config", tester.test_cpp_analyzer_custom_rules),
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if not result[0]:
                print(f"❌ {test_name} still failing")
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
        
        print()  # Add spacing between tests
    
    # Final results
    print("=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"📈 Success Rate: {success_rate:.1f}%")
    print("=" * 60)
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())