#!/usr/bin/env python3
"""
OAuth Debug Test Script

This script helps debug OAuth issues by testing the OAuth flow step by step.
"""

import asyncio
import httpx
import json
from github_oauth import GitHubOAuth

async def test_oauth_flow():
    """Test the OAuth flow step by step"""
    print("🔍 Testing GitHub OAuth Configuration...")
    
    # Test 1: Check environment variables
    print("\n1. Checking environment variables...")
    oauth = GitHubOAuth()
    
    print(f"   Client ID: {oauth.config.client_id[:10]}..." if oauth.config.client_id else "   ❌ Client ID not set")
    print(f"   Client Secret: {'✓ Set' if oauth.config.client_secret else '❌ Not set'}")
    print(f"   Redirect URI: {oauth.config.redirect_uri}")
    print(f"   Scope: {oauth.config.scope}")
    
    # Test 2: Generate authorization URL
    print("\n2. Testing authorization URL generation...")
    try:
        auth_url, state = oauth.generate_authorization_url()
        print(f"   ✓ Authorization URL generated")
        print(f"   State: {state[:20]}...")
        print(f"   URL: {auth_url[:100]}...")
    except Exception as e:
        print(f"   ❌ Error generating auth URL: {e}")
        return
    
    # Test 3: Check if the app is running
    print("\n3. Checking if the main app is running...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:10007/health")
            if response.status_code == 200:
                print("   ✓ Main app is running")
            else:
                print(f"   ⚠️  Main app responded with status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Main app not running: {e}")
        print("   💡 Start the app with: python main_app.py")
        return
    
    # Test 4: Check OAuth states endpoint
    print("\n4. Checking OAuth states...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:10007/debug/oauth-states")
            if response.status_code == 200:
                states_data = response.json()
                print(f"   ✓ OAuth states endpoint working")
                print(f"   Total states: {states_data['total_states']}")
                if states_data['states']:
                    print("   Current states:")
                    for state, data in states_data['states'].items():
                        print(f"     - {state[:20]}... (used: {data['used']})")
                else:
                    print("   No states currently stored")
            else:
                print(f"   ⚠️  OAuth states endpoint returned: {response.status_code}")
    except Exception as e:
        print(f"   ❌ OAuth states endpoint error: {e}")
    
    print("\n🎯 Next steps:")
    print("1. Make sure your GitHub OAuth app is configured with redirect URI: http://localhost:10007/auth/callback")
    print("2. Start the main app: python main_app.py")
    print("3. Visit: http://localhost:10007")
    print("4. Click 'Continue with GitHub'")
    print("5. Check the logs for detailed error information")

if __name__ == "__main__":
    asyncio.run(test_oauth_flow())
