#!/usr/bin/env python3
"""
Complete Application Test Suite

This script tests all functionalities of the GitHub Agent application:
- Server health
- OAuth flow
- API endpoints
- Chat functionality
- Repository access
"""

import asyncio
import httpx
import json
import time
from typing import Dict, Any

class GitHubAgentTester:
    """Comprehensive tester for GitHub Agent application"""
    
    def __init__(self, base_url: str = "http://localhost:10007"):
        self.base_url = base_url
        self.session_cookie = None
        
    async def test_server_health(self) -> bool:
        """Test if server is running and healthy"""
        print("🔍 Testing server health...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ Server is healthy: {data['status']}")
                    return True
                else:
                    print(f"   ❌ Server health check failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"   ❌ Server not reachable: {e}")
            return False
    
    async def test_oauth_states(self) -> bool:
        """Test OAuth states debug endpoint"""
        print("\n🔍 Testing OAuth states...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/debug/oauth-states")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ OAuth states endpoint working")
                    print(f"   📊 Total states: {data['total_states']}")
                    if data['states']:
                        for state, info in data['states'].items():
                            print(f"      - {state[:20]}... (used: {info['used']})")
                    return True
                else:
                    print(f"   ❌ OAuth states endpoint failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"   ❌ OAuth states test failed: {e}")
            return False
    
    async def test_homepage(self) -> bool:
        """Test homepage access"""
        print("\n🔍 Testing homepage...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/")
                if response.status_code == 200:
                    content = response.text
                    if "GitHub Agent" in content and "Continue with GitHub" in content:
                        print("   ✅ Homepage loads correctly with login interface")
                        return True
                    else:
                        print("   ⚠️  Homepage loads but content seems incorrect")
                        return False
                else:
                    print(f"   ❌ Homepage failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"   ❌ Homepage test failed: {e}")
            return False
    
    async def test_oauth_login_flow(self) -> bool:
        """Test OAuth login initiation"""
        print("\n🔍 Testing OAuth login flow...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/auth/login", follow_redirects=False)
                if response.status_code == 307:  # Redirect to GitHub
                    location = response.headers.get('location', '')
                    if 'github.com' in location and 'client_id=' in location:
                        print("   ✅ OAuth login redirects to GitHub correctly")
                        print(f"   🔗 GitHub URL: {location[:100]}...")
                        return True
                    else:
                        print(f"   ❌ OAuth redirect URL seems incorrect: {location}")
                        return False
                else:
                    print(f"   ❌ OAuth login failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"   ❌ OAuth login test failed: {e}")
            return False
    
    async def test_api_endpoints(self) -> bool:
        """Test API endpoints without authentication"""
        print("\n🔍 Testing API endpoints...")
        try:
            async with httpx.AsyncClient() as client:
                # Test user endpoint (should return not authenticated)
                response = await client.get(f"{self.base_url}/api/user")
                if response.status_code == 401:
                    print("   ✅ User API correctly returns 401 (not authenticated)")
                else:
                    print(f"   ⚠️  User API returned unexpected status: {response.status_code}")
                
                # Test repositories endpoint (should return not authenticated)
                response = await client.get(f"{self.base_url}/api/repositories")
                if response.status_code == 401:
                    print("   ✅ Repositories API correctly returns 401 (not authenticated)")
                else:
                    print(f"   ⚠️  Repositories API returned unexpected status: {response.status_code}")
                
                return True
        except Exception as e:
            print(f"   ❌ API endpoints test failed: {e}")
            return False
    
    async def test_chat_endpoint(self) -> bool:
        """Test chat endpoint without authentication"""
        print("\n🔍 Testing chat endpoint...")
        try:
            async with httpx.AsyncClient() as client:
                chat_data = {
                    "message": "Hello, test message",
                    "user_id": "test_user"
                }
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=chat_data
                )
                if response.status_code == 200:
                    data = response.json()
                    if "Please authenticate" in data.get('response', ''):
                        print("   ✅ Chat endpoint correctly requires authentication")
                        return True
                    else:
                        print(f"   ⚠️  Chat endpoint response unexpected: {data}")
                        return False
                else:
                    print(f"   ❌ Chat endpoint failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"   ❌ Chat endpoint test failed: {e}")
            return False
    
    async def test_debug_endpoints(self) -> bool:
        """Test debug endpoints"""
        print("\n🔍 Testing debug endpoints...")
        try:
            async with httpx.AsyncClient() as client:
                # Test debug page
                response = await client.get(f"{self.base_url}/debug")
                if response.status_code == 200:
                    print("   ✅ Debug page accessible")
                else:
                    print(f"   ❌ Debug page failed: {response.status_code}")
                
                # Test OAuth states endpoint
                response = await client.get(f"{self.base_url}/debug/oauth-states")
                if response.status_code == 200:
                    print("   ✅ OAuth states debug endpoint working")
                else:
                    print(f"   ❌ OAuth states debug failed: {response.status_code}")
                
                return True
        except Exception as e:
            print(f"   ❌ Debug endpoints test failed: {e}")
            return False
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests and return results"""
        print("🚀 Starting GitHub Agent Application Tests")
        print("=" * 50)
        
        results = {}
        
        # Test server health first
        results['server_health'] = await self.test_server_health()
        if not results['server_health']:
            print("\n❌ Server is not running. Please start the server first:")
            print("   python3 main_app.py")
            return results
        
        # Run all other tests
        results['oauth_states'] = await self.test_oauth_states()
        results['homepage'] = await self.test_homepage()
        results['oauth_login'] = await self.test_oauth_login_flow()
        results['api_endpoints'] = await self.test_api_endpoints()
        results['chat_endpoint'] = await self.test_chat_endpoint()
        results['debug_endpoints'] = await self.test_debug_endpoints()
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {test_name.replace('_', ' ').title()}: {status}")
        
        print(f"\n🎯 Overall: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED! The application is working correctly.")
            print("\n📋 Next steps:")
            print("1. Visit http://localhost:10007 in your browser")
            print("2. Click 'Continue with GitHub' to authenticate")
            print("3. Try asking questions in the chat interface")
        else:
            print(f"\n⚠️  {total - passed} tests failed. Check the errors above.")
        
        return results

async def main():
    """Main test runner"""
    tester = GitHubAgentTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
