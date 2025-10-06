# GitHub OAuth Setup Guide

This guide explains how to set up GitHub OAuth authentication for the GitHub Agent instead of using personal access tokens.

## Overview

The OAuth implementation provides:
- Secure user authentication with GitHub
- Access to both public and private repositories
- Better security than personal access tokens
- User-controlled access permissions

## Setup Steps

### 1. Create GitHub OAuth App

1. Go to [GitHub Settings > Developer settings > OAuth Apps](https://github.com/settings/applications/new)
2. Click "New OAuth App"
3. Fill in the details:
   - **Application name**: `GitHub Agent`
   - **Homepage URL**: `http://localhost:10007`
   - **Authorization callback URL**: `http://localhost:10007/auth/callback`
4. Click "Register application"
5. Copy the **Client ID** and **Client Secret**

### 2. Environment Configuration

Create a `.env` file in the project root:

```bash
# GitHub OAuth Configuration
GITHUB_CLIENT_ID=your_github_client_id_here
GITHUB_CLIENT_SECRET=your_github_client_secret_here
GITHUB_REDIRECT_URI=http://localhost:10007/auth/callback
GITHUB_OAUTH_SCOPE=repo,user,read:org

# Fallback GitHub Token (optional, for backward compatibility)
GITHUB_TOKEN=your_github_token_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Server Configuration
OAUTH_SERVER_PORT=8001
MAIN_SERVER_PORT=10007
```

### 3. Install Dependencies

The required dependencies are already included in `pyproject.toml`:
- `fastapi` - For OAuth endpoints
- `httpx` - For HTTP requests
- `uvicorn` - For running the OAuth server

### 4. Running the OAuth Server

Start the OAuth server:

```bash
python run_oauth_server.py
```

This will start the OAuth server on port 8001 (configurable via `OAUTH_SERVER_PORT`).

### 5. Integration with Main Agent

The main agent can now be configured to use OAuth by passing a `user_id` parameter:

```python
from openai_agent import create_agent

# Create agent with OAuth authentication
agent_config = create_agent(user_id="user123")
```

## OAuth Flow

### 1. User Authentication

1. User visits: `http://localhost:8001/auth/login`
2. Server generates authorization URL and returns it
3. User is redirected to GitHub for authentication
4. GitHub redirects back to: `http://localhost:10007/auth/callback`
5. Server exchanges code for access token
6. Token is stored for the user

### 2. Using Authenticated Agent

Once authenticated, the agent will automatically use the user's OAuth token to access their repositories.

## API Endpoints

The OAuth server provides these endpoints:

- `GET /auth/login` - Initiate OAuth flow
- `GET /auth/callback` - Handle OAuth callback
- `GET /auth/status/{user_id}` - Check authentication status
- `POST /auth/logout/{user_id}` - Logout user
- `GET /auth/users` - List authenticated users
- `GET /auth/token/{user_id}` - Get user token info
- `GET /health` - Health check

## Security Considerations

1. **Token Storage**: Currently uses in-memory storage. For production, use Redis or a database.
2. **HTTPS**: Use HTTPS in production for secure token transmission.
3. **Token Expiration**: GitHub tokens don't expire by default, but you can implement token refresh.
4. **Scope Management**: Only request necessary scopes (`repo`, `user`, `read:org`).

## Migration from Token-based Auth

The implementation is backward compatible:

1. If `user_id` is provided, OAuth tokens are used
2. If no `user_id` but `GITHUB_TOKEN` is set, fallback to token auth
3. If neither, unauthenticated access (public repos only)

## Troubleshooting

### Common Issues

1. **"GitHub OAuth not configured"**
   - Ensure `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` are set

2. **"Authorization code not provided"**
   - Check that the callback URL matches your OAuth app configuration

3. **"Token exchange failed"**
   - Verify client secret is correct
   - Check that the authorization code hasn't expired

4. **"User not authenticated"**
   - User needs to complete OAuth flow first
   - Check that token storage is working

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Production Deployment

For production:

1. Use a proper database for token storage
2. Implement token refresh mechanism
3. Use HTTPS for all endpoints
4. Set up proper monitoring and logging
5. Consider using environment-specific OAuth apps

## Example Usage

```python
# Start OAuth server
python run_oauth_server.py

# In another terminal, start main agent
python -m a2a.server.main --port 10007

# Authenticate user
curl http://localhost:8001/auth/login

# Use authenticated agent
# The agent will automatically use OAuth tokens when user_id is provided
```
