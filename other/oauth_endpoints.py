from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import logging
from github_oauth import GitHubOAuth, token_storage, OAuthToken

logger = logging.getLogger(__name__)

# Create FastAPI app for OAuth endpoints
oauth_app = FastAPI(title="GitHub OAuth", version="1.0.0")

# Add CORS middleware
oauth_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:10007", "http://localhost:3000"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OAuth handler
oauth_handler = GitHubOAuth()


@oauth_app.get("/auth/login")
async def login(request: Request):
    """Initiate GitHub OAuth login flow
    
    Returns:
        RedirectResponse: Redirects to GitHub authorization page
    """
    try:
        auth_url, state = oauth_handler.generate_authorization_url()
        
        # Store state in session or return it to frontend
        # For simplicity, we'll return it in the response
        return JSONResponse({
            "auth_url": auth_url,
            "state": state,
            "message": "Redirect user to auth_url to complete authentication"
        })
    except Exception as e:
        logger.error(f"Error initiating OAuth flow: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate OAuth: {str(e)}")


@oauth_app.get("/auth/callback")
async def callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
):
    """Handle GitHub OAuth callback
    
    Args:
        code: Authorization code from GitHub
        state: State parameter for verification
        error: Error code if authorization failed
        error_description: Error description if authorization failed
        
    Returns:
        JSONResponse: Success or error response
    """
    try:
        if error:
            logger.error(f"OAuth error: {error} - {error_description}")
            return JSONResponse({
                "success": False,
                "error": error,
                "error_description": error_description
            }, status_code=400)
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code not provided")
        
        # Exchange code for token
        token = await oauth_handler.exchange_code_for_token(code, state or "")
        
        # Store token
        if token.user_id:
            token_storage.store_token(token.user_id, token)
            logger.info(f"Token stored for user: {token.user_login}")
        
        return JSONResponse({
            "success": True,
            "user_id": token.user_id,
            "user_login": token.user_login,
            "message": "Authentication successful"
        })
        
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        return JSONResponse({
            "success": False,
            "error": "authentication_failed",
            "error_description": str(e)
        }, status_code=500)


@oauth_app.get("/auth/status/{user_id}")
async def get_auth_status(user_id: str):
    """Check authentication status for a user
    
    Args:
        user_id: User identifier
        
    Returns:
        JSONResponse: Authentication status
    """
    try:
        token = token_storage.get_token(user_id)
        
        if not token:
            return JSONResponse({
                "authenticated": False,
                "message": "User not authenticated"
            })
        
        # Validate token
        is_valid = oauth_handler.validate_token(token)
        
        if not is_valid:
            # Remove invalid token
            token_storage.remove_token(user_id)
            return JSONResponse({
                "authenticated": False,
                "message": "Token expired or invalid"
            })
        
        return JSONResponse({
            "authenticated": True,
            "user_login": token.user_login,
            "scope": token.scope,
            "message": "User is authenticated"
        })
        
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return JSONResponse({
            "authenticated": False,
            "error": str(e)
        }, status_code=500)


@oauth_app.post("/auth/logout/{user_id}")
async def logout(user_id: str):
    """Logout user and remove stored token
    
    Args:
        user_id: User identifier
        
    Returns:
        JSONResponse: Logout status
    """
    try:
        token_storage.remove_token(user_id)
        logger.info(f"User {user_id} logged out")
        
        return JSONResponse({
            "success": True,
            "message": "Logged out successfully"
        })
        
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@oauth_app.get("/auth/users")
async def list_authenticated_users():
    """List all authenticated users
    
    Returns:
        JSONResponse: List of authenticated users
    """
    try:
        users = token_storage.list_users()
        return JSONResponse({
            "users": users,
            "count": len(users)
        })
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return JSONResponse({
            "error": str(e)
        }, status_code=500)


@oauth_app.get("/auth/token/{user_id}")
async def get_user_token(user_id: str):
    """Get user's OAuth token (for internal use)
    
    Args:
        user_id: User identifier
        
    Returns:
        JSONResponse: Token information (without sensitive data)
    """
    try:
        token = token_storage.get_token(user_id)
        
        if not token:
            raise HTTPException(status_code=404, detail="User not authenticated")
        
        # Return token info without the actual access token for security
        return JSONResponse({
            "user_id": token.user_id,
            "user_login": token.user_login,
            "scope": token.scope,
            "token_type": token.token_type,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user token: {e}")
        return JSONResponse({
            "error": str(e)
        }, status_code=500)


# Health check endpoint
@oauth_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "GitHub OAuth"
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(oauth_app, host="0.0.0.0", port=8001)
