#!/usr/bin/env python3
"""
Main GitHub Agent Application

This is the main application that integrates:
- GitHub OAuth authentication
- A2A agent execution
- Web UI for chat interface
- Session management
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio
from fastapi import FastAPI, Request, HTTPException, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

# Import our modules
from github_oauth import token_storage, GitHubOAuth
from simple_agent_executor import SimpleGitHubAgent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="GitHub Agent Chat",
    description="AI-powered GitHub repository assistant with OAuth authentication",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates for web UI
templates = Jinja2Templates(directory="templates")

# OAuth handler
oauth_handler = GitHubOAuth()

# In-memory session storage (use Redis in production)
sessions: Dict[str, Dict[str, Any]] = {}

# OAuth state storage (use Redis in production)
oauth_states: Dict[str, Dict[str, Any]] = {}

class ChatMessage(BaseModel):
    message: str
    user_id: str

class ChatResponse(BaseModel):
    response: str
    status: str
    error: Optional[str] = None

class UserSession(BaseModel):
    user_id: str
    user_login: str
    authenticated: bool
    created_at: datetime
    last_activity: datetime

def get_session_id(request: Request) -> str:
    """Get or create session ID from request"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        import secrets
        session_id = secrets.token_urlsafe(32)
    return session_id

def get_user_session(session_id: str) -> Optional[UserSession]:
    """Get user session from session ID"""
    session_data = sessions.get(session_id)
    if not session_data:
        return None
    
    return UserSession(**session_data)

def create_user_session(user_id: str, user_login: str) -> str:
    """Create a new user session"""
    import secrets
    session_id = secrets.token_urlsafe(32)
    now = datetime.now()
    
    sessions[session_id] = {
        "user_id": user_id,
        "user_login": user_login,
        "authenticated": True,
        "created_at": now.isoformat(),
        "last_activity": now.isoformat()
    }
    
    return session_id

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    """Main homepage - shows login or chat interface"""
    session_id = get_session_id(request)
    user_session = get_user_session(session_id)
    
    if user_session and user_session.authenticated:
        # User is authenticated, show chat interface
        return templates.TemplateResponse("chat.html", {
            "request": request,
            "user_login": user_session.user_login,
            "user_id": user_session.user_id
        })
    else:
        # User not authenticated, show login page
        return templates.TemplateResponse("login.html", {
            "request": request
        })

@app.get("/auth/login")
async def login(request: Request):
    """Initiate GitHub OAuth login"""
    try:
        auth_url, state = oauth_handler.generate_authorization_url()
        
        # Clean up old states (older than 10 minutes) - but be more conservative
        now = datetime.now()
        expired_states = []
        for state_key, state_data in oauth_states.items():
            if 'created_at' in state_data:
                created_at = datetime.fromisoformat(state_data['created_at'])
                if (now - created_at).total_seconds() > 600:  # 10 minutes
                    expired_states.append(state_key)
        
        for expired_state in expired_states:
            del oauth_states[expired_state]
            logger.info(f"Cleaned up expired state: {expired_state[:20]}...")
        
        # Store state in global state store for verification
        oauth_states[state] = {
            'created_at': datetime.now().isoformat(),
            'used': False
        }
        
        logger.info(f"Generated OAuth state: {state[:20]}... (Total states: {len(oauth_states)})")
        logger.info(f"Stored state data: {oauth_states[state]}")
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Error initiating OAuth: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate OAuth login")

@app.get("/auth/callback")
async def oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """Handle GitHub OAuth callback"""
    try:
        logger.info(f"OAuth callback received - code: {code[:10] if code else 'None'}..., state: {state[:20] if state else 'None'}...")
        
        if error:
            logger.error(f"OAuth error: {error}")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": f"OAuth error: {error}"
            })
        
        if not code:
            logger.error("Authorization code not provided")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Authentication failed: 400: Authorization code not provided"
            })
        
        if not state:
            logger.error("State parameter not provided")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Authentication failed: 400: Invalid state parameter"
            })
        
        # Verify state using global state store
        logger.info(f"Available OAuth states: {list(oauth_states.keys())[:3]}...")
        logger.info(f"Looking for state: {state[:20]}...")
        
        if state not in oauth_states:
            logger.error(f"State {state[:20]}... not found in oauth_states")
            logger.error(f"Available states: {list(oauth_states.keys())}")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Authentication failed: 400: Invalid state parameter"
            })
        
        if oauth_states[state]['used']:
            logger.error(f"State {state[:20]}... already used")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Authentication failed: 400: State already used"
            })
        
        # Mark state as used
        oauth_states[state]['used'] = True
        logger.info(f"State {state[:20]}... marked as used")
        
        # Exchange code for token
        token = await oauth_handler.exchange_code_for_token(code, state)
        
        if not token.user_id or not token.user_login:
            logger.error("Failed to get user information from token")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Authentication failed: Failed to get user information"
            })
        
        logger.info(f"Token exchange successful for user: {token.user_login}")
        
        # Store token
        token_storage.store_token(token.user_id, token)
        
        # Create user session
        session_id = create_user_session(token.user_id, token.user_login)
        
        # Redirect to homepage with session cookie
        response = RedirectResponse(url="/")
        response.set_cookie(key="session_id", value=session_id, httponly=True, secure=False)
        logger.info(f"User {token.user_login} authenticated successfully")
        return response
        
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"Authentication failed: {str(e)}"
        })

@app.get("/auth/logout")
async def logout(request: Request):
    """Logout user"""
    session_id = get_session_id(request)
    user_session = get_user_session(session_id)
    
    if user_session:
        # Remove token
        token_storage.remove_token(user_session.user_id)
        # Remove session
        sessions.pop(session_id, None)
    
    response = RedirectResponse(url="/")
    response.delete_cookie(key="session_id")
    return response

@app.get("/api/user")
async def get_user_info(request: Request):
    """Get current user information"""
    session_id = get_session_id(request)
    user_session = get_user_session(session_id)
    
    if not user_session or not user_session.authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return {
        "user_id": user_session.user_id,
        "user_login": user_session.user_login,
        "authenticated": True
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_agent(request: Request, chat_message: ChatMessage):
    """Chat with the GitHub agent"""
    try:
        session_id = get_session_id(request)
        user_session = get_user_session(session_id)
        
        if not user_session or not user_session.authenticated:
            return ChatResponse(
                response="Please authenticate with GitHub first.",
                status="error",
                error="Not authenticated"
            )
        
        # Create simplified agent
        agent = SimpleGitHubAgent(
            user_id=user_session.user_id,
            api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        )
        
        # Process the message
        response_text = await agent.chat(chat_message.message)
        
        return ChatResponse(
            response=response_text,
            status="success"
        )
        
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return ChatResponse(
            response="Sorry, I encountered an error processing your request.",
            status="error",
            error=str(e)
        )

@app.get("/api/repositories")
async def get_user_repositories(request: Request):
    """Get user's repositories"""
    try:
        session_id = get_session_id(request)
        user_session = get_user_session(session_id)
        
        if not user_session or not user_session.authenticated:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Create simplified agent to get repositories
        agent = SimpleGitHubAgent(
            user_id=user_session.user_id,
            api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        )
        
        # Get repositories
        result = await agent.get_user_repositories()
        
        if result["status"] == "success":
            return {
                "repositories": [
                    {
                        "name": repo.name,
                        "full_name": repo.full_name,
                        "description": repo.description,
                        "url": repo.url,
                        "private": repo.private,
                        "updated_at": repo.updated_at,
                        "stars": repo.stars,
                        "forks": repo.forks
                    }
                    for repo in result["data"] or []
                ],
                "count": result["count"]
            }
        else:
            raise HTTPException(status_code=500, detail=result["message"])
            
    except Exception as e:
        logger.error(f"Error getting repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug", response_class=HTMLResponse)
async def debug_page(request: Request):
    """Debug page for OAuth testing"""
    return templates.TemplateResponse("debug.html", {"request": request})

@app.get("/debug/oauth-states")
async def debug_oauth_states():
    """Debug endpoint to check OAuth states"""
    return {
        "total_states": len(oauth_states),
        "states": {
            state: {
                "created_at": data.get('created_at'),
                "used": data.get('used', False)
            }
            for state, data in oauth_states.items()
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "GitHub Agent Chat"}

if __name__ == "__main__":
    import uvicorn
    
    # Render provides PORT environment variable
    port = int(os.getenv("PORT", os.getenv("MAIN_SERVER_PORT", 8000)))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(app, host=host, port=port)
