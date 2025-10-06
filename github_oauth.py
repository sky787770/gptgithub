import os
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode, parse_qs
import httpx
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class OAuthConfig(BaseModel):
    """GitHub OAuth configuration"""
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str 
    state_length: int = 32


class OAuthToken(BaseModel):
    """OAuth token information"""
    access_token: str
    token_type: str = "bearer"
    scope: str
    expires_at: Optional[datetime] = None
    refresh_token: Optional[str] = None
    user_id: Optional[str] = None
    user_login: Optional[str] = None


class GitHubOAuth:
    """GitHub OAuth authentication handler"""
    
    def __init__(self):
        self.config = OAuthConfig(
            client_id=os.getenv('GITHUB_CLIENT_ID', ''),
            client_secret=os.getenv('GITHUB_CLIENT_SECRET', ''),
            redirect_uri=os.getenv('GITHUB_REDIRECT_URI', ''),
            scope=os.getenv('GITHUB_OAUTH_SCOPE', '')
        )
        self.base_url = "https://github.com"
        self.api_url = "https://api.github.com"
        
    def generate_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """Generate GitHub OAuth authorization URL
        
        Returns:
            tuple: (authorization_url, state) - URL to redirect user to and state for verification
        """
        if not state:
            state = secrets.token_urlsafe(self.config.state_length)
            
        params = {
            'client_id': self.config.client_id,
            'redirect_uri': self.config.redirect_uri,
            'scope': self.config.scope,
            'state': state,
            'allow_signup': 'true'
        }
        
        auth_url = f"{self.base_url}/login/oauth/authorize?{urlencode(params)}"
        return auth_url, state
    
    async def exchange_code_for_token(self, code: str, state: str) -> OAuthToken:
        """Exchange authorization code for access token
        
        Args:
            code: Authorization code from GitHub
            state: State parameter for verification
            
        Returns:
            OAuthToken: Token information
            
        Raises:
            ValueError: If token exchange fails
        """
        if not self.config.client_id or not self.config.client_secret:
            raise ValueError("GitHub OAuth not configured. Please set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET")
            
        data = {
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'code': code,
            'redirect_uri': self.config.redirect_uri
        }
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/login/oauth/access_token",
                data=data,
                headers=headers
            )
            
        if response.status_code != 200:
            raise ValueError(f"Token exchange failed: {response.status_code} - {response.text}")
            
        token_data = response.json()
        
        if 'error' in token_data:
            raise ValueError(f"OAuth error: {token_data['error_description']}")
            
        # Get user information
        user_info = await self._get_user_info(token_data['access_token'])
        
        return OAuthToken(
            access_token=token_data['access_token'],
            token_type=token_data.get('token_type', 'bearer'),
            scope=token_data.get('scope', ''),
            user_id=str(user_info.get('id', '')),
            user_login=user_info.get('login', ''),
            expires_at=None  # GitHub tokens don't expire by default
        )
    
    async def _get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from GitHub API
        
        Args:
            access_token: GitHub access token
            
        Returns:
            Dict: User information
        """
        headers = {
            'Authorization': f'token {access_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/user",
                headers=headers
            )
            
        if response.status_code != 200:
            raise ValueError(f"Failed to get user info: {response.status_code}")
            
        return response.json()
    
    async def refresh_token(self, refresh_token: str) -> OAuthToken:
        """Refresh access token (GitHub doesn't support refresh tokens by default)
        
        Args:
            refresh_token: Refresh token (not used for GitHub)
            
        Returns:
            OAuthToken: New token information
            
        Raises:
            NotImplementedError: GitHub doesn't support refresh tokens
        """
        raise NotImplementedError("GitHub OAuth doesn't support refresh tokens")
    
    def validate_token(self, token: OAuthToken) -> bool:
        """Validate if token is still valid
        
        Args:
            token: OAuth token to validate
            
        Returns:
            bool: True if token is valid
        """
        if not token.access_token:
            return False
            
        if token.expires_at and token.expires_at < datetime.now():
            return False
            
        return True
    
    def get_authorization_header(self, token: OAuthToken) -> Dict[str, str]:
        """Get authorization header for API requests
        
        Args:
            token: OAuth token
            
        Returns:
            Dict: Authorization header
        """
        return {
            'Authorization': f'{token.token_type} {token.access_token}',
            'Accept': 'application/vnd.github.v3+json'
        }


class TokenStorage:
    """Simple in-memory token storage (in production, use Redis or database)"""
    
    def __init__(self):
        self._tokens: Dict[str, OAuthToken] = {}
    
    def store_token(self, user_id: str, token: OAuthToken) -> None:
        """Store token for user
        
        Args:
            user_id: User identifier
            token: OAuth token
        """
        self._tokens[user_id] = token
    
    def get_token(self, user_id: str) -> Optional[OAuthToken]:
        """Get token for user
        
        Args:
            user_id: User identifier
            
        Returns:
            OAuthToken or None if not found
        """
        return self._tokens.get(user_id)
    
    def remove_token(self, user_id: str) -> None:
        """Remove token for user
        
        Args:
            user_id: User identifier
        """
        self._tokens.pop(user_id, None)
    
    def list_users(self) -> list[str]:
        """List all users with stored tokens
        
        Returns:
            List of user IDs
        """
        return list(self._tokens.keys())


# Global token storage instance
token_storage = TokenStorage()
