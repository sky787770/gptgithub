#!/usr/bin/env python3
"""
Simplified Agent Executor for Chat Interface

This module provides a simplified way to execute the GitHub agent
without the full A2A framework complexity, making it easier to integrate
with the web chat interface.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from github_toolset import GitHubToolset
from github_oauth import token_storage

logger = logging.getLogger(__name__)

class SimpleGitHubAgent:
    """Simplified GitHub Agent for chat interface"""
    
    def __init__(self, user_id: str, api_key: str):
        self.user_id = user_id
        self.api_key = api_key
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url='https://openrouter.ai/api/v1',
            default_headers={
                'HTTP-Referer': 'http://localhost:10007',
                'X-Title': 'GitHub Agent',
            },
        )
        self.model = 'anthropic/claude-3.5-sonnet'
        self.toolset = GitHubToolset(user_id=user_id)
        
    async def chat(self, message: str) -> str:
        """Process a chat message and return response"""
        try:
            # Get user's OAuth token
            oauth_token = token_storage.get_token(self.user_id)
            if not oauth_token or not oauth_token.access_token:
                return "❌ You need to authenticate with GitHub first. Please log out and log back in."
            
            # Create system prompt
            system_prompt = f"""You are a GitHub agent that can help users query information about GitHub repositories and recent project updates.

You are authenticated as user {self.user_id} via OAuth. Use their GitHub repositories and data.

Users will request information about:
- Recent updates to their repositories
- Recent commits in specific repositories  
- Search for repositories with recent activity
- General GitHub project information
- Security flows in specific repositories
- Whether best practices were followed or not
- Code review related to specific repositories

Use the provided tools for interacting with the GitHub API.

When displaying repository information, include relevant details like:
- Repository name and description
- Last updated time
- Programming language
- Stars and forks count
- Recent commit information when available

Always provide helpful and accurate information based on the GitHub API results. Respond in English by default.

IMPORTANT: Be conversational and helpful. Format your responses nicely with emojis and clear structure."""

            # Convert tools to OpenAI format
            openai_tools = []
            tools_dict = self.toolset.get_tools()
            
            for tool_name, tool_instance in tools_dict.items():
                if hasattr(tool_instance, tool_name):
                    func = getattr(tool_instance, tool_name)
                    schema = self._extract_function_schema(func)
                    openai_tools.append({'type': 'function', 'function': schema})

            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': message},
            ]

            max_iterations = 5
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                try:
                    # Make API call to OpenAI
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        tools=openai_tools if openai_tools else None,
                        tool_choice='auto' if openai_tools else None,
                        temperature=0.1,
                        max_tokens=4000,
                    )

                    message_obj = response.choices[0].message

                    # Add assistant's response to messages
                    messages.append({
                        'role': 'assistant',
                        'content': message_obj.content,
                        'tool_calls': message_obj.tool_calls,
                    })

                    # Check if there are tool calls to execute
                    if message_obj.tool_calls:
                        # Execute tool calls
                        for tool_call in message_obj.tool_calls:
                            function_name = tool_call.function.name
                            function_args = json.loads(tool_call.function.arguments)

                            logger.debug(f'Calling function: {function_name} with args: {function_args}')

                            # Execute the function
                            if function_name in tools_dict:
                                tool_instance = tools_dict[function_name]
                                if hasattr(tool_instance, function_name):
                                    method = getattr(tool_instance, function_name)
                                    result = method(**function_args)
                                else:
                                    result = {
                                        'error': f'Method {function_name} not found on tool instance'
                                    }
                            else:
                                result = {
                                    'error': f'Function {function_name} not found'
                                }

                            # Serialize result properly
                            if hasattr(result, 'model_dump'):
                                result_json = json.dumps(result.model_dump())
                            elif isinstance(result, dict):
                                result_json = json.dumps(result)
                            else:
                                result_json = str(result)

                            # Add tool result to messages
                            messages.append({
                                'role': 'tool',
                                'tool_call_id': tool_call.id,
                                'content': result_json,
                            })

                        # Continue the loop to get the final response
                        continue
                    
                    # No more tool calls, this is the final response
                    if message_obj.content:
                        return message_obj.content
                    break

                except Exception as e:
                    logger.error(f'Error in OpenAI API call: {e}')
                    return f"❌ Sorry, an error occurred while processing your request: {str(e)}"

            return "❌ Sorry, the request has exceeded the maximum number of iterations."

        except Exception as e:
            logger.error(f'Error in chat: {e}')
            return f"❌ Sorry, I encountered an error: {str(e)}"

    def _extract_function_schema(self, func):
        """Extract OpenAI function schema from a Python function"""
        import inspect

        # Get function signature
        sig = inspect.signature(func)

        # Get docstring
        docstring = inspect.getdoc(func) or ''

        # Extract description and parameter info from docstring
        lines = docstring.split('\n')
        description = lines[0] if lines else func.__name__

        # Build parameters schema
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            param_type = 'string'  # Default type
            param_description = f'Parameter {param_name}'

            # Try to infer type from annotation
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = 'integer'
                elif param.annotation == float:
                    param_type = 'number'
                elif param.annotation == bool:
                    param_type = 'boolean'
                elif param.annotation == list:
                    param_type = 'array'
                elif param.annotation == dict:
                    param_type = 'object'

            # Check if parameter has default value
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

            properties[param_name] = {
                'type': param_type,
                'description': param_description,
            }

        return {
            'name': func.__name__,
            'description': description,
            'parameters': {
                'type': 'object',
                'properties': properties,
                'required': required,
            },
        }

    async def get_user_repositories(self) -> Dict[str, Any]:
        """Get user's repositories"""
        try:
            result = self.toolset.get_user_repositories()
            return {
                'status': result.status,
                'data': result.data,
                'count': result.count,
                'message': result.message
            }
        except Exception as e:
            logger.error(f'Error getting repositories: {e}')
            return {
                'status': 'error',
                'data': None,
                'count': 0,
                'message': str(e)
            }
