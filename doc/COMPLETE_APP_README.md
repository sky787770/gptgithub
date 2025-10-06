# 🤖 GitHub Agent - Complete Application

A user-friendly web application that allows users to chat with an AI agent about their GitHub repositories using OAuth authentication.

## ✨ Features

- **🔐 Secure OAuth Authentication** - Users authenticate directly with GitHub
- **💬 Interactive Chat Interface** - Beautiful, responsive web UI for chatting
- **📁 Repository Access** - Access to both public and private repositories
- **🤖 AI-Powered Insights** - Get intelligent answers about your code and repositories
- **📊 Real-time Data** - Live information about commits, changes, and repository activity
- **🎯 Context-Aware** - Select specific repositories for focused conversations

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10 or higher
- GitHub account
- OpenAI API key
- GitHub OAuth App (we'll help you create this)

### 2. Installation

```bash
# Clone or download the project
cd github-agent

# Install dependencies
pip install -r requirements.txt

# Or using uv (recommended)
uv sync
```

### 3. GitHub OAuth Setup

1. Go to [GitHub Settings > Developer settings > OAuth Apps](https://github.com/settings/applications/new)
2. Click "New OAuth App"
3. Fill in the details:
   - **Application name**: `GitHub Agent`
   - **Homepage URL**: `http://localhost:10007`
   - **Authorization callback URL**: `http://localhost:10007/auth/callback`
4. Click "Register application"
5. Copy the **Client ID** and **Client Secret**

### 4. Environment Configuration

Create a `.env` file in the project root:

```bash
# GitHub OAuth Configuration
GITHUB_CLIENT_ID=your_github_client_id_here
GITHUB_CLIENT_SECRET=your_github_client_secret_here
GITHUB_REDIRECT_URI=http://localhost:10007/auth/callback
GITHUB_OAUTH_SCOPE=repo,user,read:org

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Server Configuration
MAIN_SERVER_PORT=10007
```

### 5. Run the Application

```bash
python run_app.py
```

The application will be available at: **http://localhost:10007**

## 🎯 How to Use

### 1. Authentication
- Visit the application URL
- Click "Continue with GitHub"
- Authorize the application on GitHub
- You'll be redirected back to the chat interface

### 2. Chat with Your Repositories
Once authenticated, you can ask questions like:

- **"Tell me about recent changes in my repositories"**
- **"What are my most active repositories?"**
- **"Show me recent commits in [repo-name]"**
- **"Analyze the security practices in my code"**
- **"What programming languages do I use most?"**
- **"Show me recent pull requests and issues"**

### 3. Repository Selection
- Click the "My Repos" button to see your repositories
- Select specific repositories to focus the conversation
- The AI will prioritize information from selected repositories

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Browser   │◄──►│   FastAPI App    │◄──►│  GitHub OAuth   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Simple Agent    │
                       │   Executor       │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  GitHub API      │
                       │  (via OAuth)     │
                       └──────────────────┘
```

## 📁 Project Structure

```
github-agent/
├── main_app.py                 # Main FastAPI application
├── simple_agent_executor.py   # Simplified agent executor
├── github_oauth.py            # OAuth authentication
├── github_toolset.py          # GitHub API tools
├── run_app.py                 # Application runner
├── requirements.txt           # Python dependencies
├── templates/                 # HTML templates
│   ├── login.html            # Login page
│   ├── chat.html             # Chat interface
│   └── error.html            # Error page
└── .env                      # Environment configuration
```

## 🔧 Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_CLIENT_ID` | GitHub OAuth App Client ID | Required |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App Client Secret | Required |
| `GITHUB_REDIRECT_URI` | OAuth callback URL | `http://localhost:10007/auth/callback` |
| `GITHUB_OAUTH_SCOPE` | OAuth permissions | `repo,user,read:org` |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `MAIN_SERVER_PORT` | Application port | `10007` |

### OAuth Scopes

The application requests these GitHub permissions:
- `repo` - Full access to repositories (public and private)
- `user` - Read user profile information
- `read:org` - Read organization information

## 🛠️ Development

### Running in Development Mode

```bash
# Install development dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn main_app:app --reload --host 0.0.0.0 --port 10007
```

### Adding New Features

1. **New GitHub Tools**: Add methods to `github_toolset.py`
2. **UI Improvements**: Modify templates in `templates/`
3. **API Endpoints**: Add routes to `main_app.py`
4. **Agent Behavior**: Update `simple_agent_executor.py`

## 🔒 Security Considerations

- **OAuth Tokens**: Stored securely in memory (use Redis/DB in production)
- **HTTPS**: Use HTTPS in production for secure token transmission
- **Token Expiration**: GitHub tokens don't expire by default
- **Scope Management**: Only request necessary permissions
- **Session Management**: Sessions are stored in memory (use Redis in production)

## 🚀 Production Deployment

### Using Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 10007

CMD ["python", "run_app.py"]
```

### Using Environment Variables

```bash
export GITHUB_CLIENT_ID="your_client_id"
export GITHUB_CLIENT_SECRET="your_client_secret"
export OPENAI_API_KEY="your_openai_key"
export MAIN_SERVER_PORT="10007"
```

## 🐛 Troubleshooting

### Common Issues

1. **"GitHub OAuth not configured"**
   - Ensure `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` are set

2. **"Authorization code not provided"**
   - Check that the callback URL matches your OAuth app configuration

3. **"User not authenticated"**
   - User needs to complete OAuth flow first
   - Check that token storage is working

4. **"OpenAI API error"**
   - Verify your OpenAI API key is valid
   - Check your OpenAI account has sufficient credits

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📊 Example Conversations

### Repository Analysis
**User**: "Tell me about recent changes in my a2a-tck repository"

**Agent**: "I'll analyze the recent changes in your a2a-tck repository. Let me fetch the latest commits and changes for you..."

### Security Review
**User**: "Are there any security issues in my code?"

**Agent**: "I'll review your repositories for potential security issues. Let me check for common security patterns and best practices..."

### Activity Overview
**User**: "What are my most active repositories this month?"

**Agent**: "Based on recent activity, here are your most active repositories: [list with details]..."

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

If you encounter any issues:

1. Check the troubleshooting section above
2. Review the logs for error messages
3. Ensure all environment variables are set correctly
4. Verify your GitHub OAuth app configuration

## 🎉 Success!

You now have a fully functional GitHub Agent application that allows users to:

✅ Authenticate securely with GitHub OAuth  
✅ Chat with an AI about their repositories  
✅ Access both public and private repository data  
✅ Get intelligent insights about their code  
✅ Use a beautiful, responsive web interface  

The application is ready for both development and production use!
