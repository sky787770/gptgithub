import json
import logging

from typing import Any

from a2a.server.agent_execution import AgentExecutor # AgentExecutor: Executes the agent's code.
from a2a.server.agent_execution.context import RequestContext # RequestContext: Contains information about the current request (like who asked what)
from a2a.server.events.event_queue import EventQueue # EventQueue: Manages events (like messages, tasks, and artifacts).
from a2a.server.tasks import TaskUpdater # TaskUpdater: Updates the task status and adds artifacts (like the response) to the task.
from a2a.types import (
    AgentCard, # AgentCard: Contains information about the agent (like its name, description, skills, security, and capabilities).
    TaskState, # TaskState: Represents the current state of the task (like working, completed, failed, etc.).
    TextPart, # TextPart: Represents a part of the response (like a text message).
    UnsupportedOperationError, # UnsupportedOperationError: Raised when an operation is not supported or things that this agent can't do.
)
from a2a.utils.errors import ServerError # ServerError: Raised when an error occurs in the server.
from openai import AsyncOpenAI # AsyncOpenAI: Asynchronous OpenAI client.


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class OpenAIAgentExecutor(AgentExecutor):
    """An AgentExecutor that runs an OpenAI-based Agent."""

    def __init__(
        self,
        card: AgentCard,
        tools: dict[str, Any],
        api_key: str,
        system_prompt: str, #Instructions for how the AI should behave
        user_id: str | None = None,
    ):
        self._card = card
        self.tools = tools
        self.user_id = user_id
        self.client = AsyncOpenAI(   # Creates an OpenAI client that connects to OpenRouter 
            api_key=api_key,
            base_url='https://openrouter.ai/api/v1',
            default_headers={  # The headers help identify where requests are coming from
                # They contain information about the request, like the URL of the page that made the request.
                'HTTP-Referer': 'http://localhost:10007',
                'X-Title': 'GitHub Agent',
            },
        )
        self.model = 'anthropic/claude-3.5-sonnet'
        self.system_prompt = system_prompt

    async def _process_request( # This is the main method that processes user requests. It's async which means it can wait for things to complete without blocking.
        self, 
        message_text: str,
        context: RequestContext,
        task_updater: TaskUpdater, # Updates the task status and adds artifacts (like the response) to the task.
    ) -> None:
        messages = [
            {'role': 'system', 'content': self.system_prompt}, #'system' role is for instructions for how the AI should behave
            {'role': 'user', 'content': message_text}, #'user' role is for the user's request(What the user asked).
        ]

        # This converts the agent's tools into a format that OpenAI can understand.
        openai_tools = []
        for tool_name, tool_instance in self.tools.items():
            if hasattr(tool_instance, tool_name):
                func = getattr(tool_instance, tool_name)
                # Extract function schema from the method
                schema = self._extract_function_schema(func)
                openai_tools.append({'type': 'function', 'function': schema})

        max_iterations = 10 # The maximum number of times the agent will try to process the request, if it fails. will not run forever.
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

                message = response.choices[0].message

                # Gets the AI's response and adds it to the conversation history(messages).
                messages.append(
                    {
                        'role': 'assistant',
                        'content': message.content,
                        'tool_calls': message.tool_calls,
                    }
                )

                # Check if there are tool calls to execute or If the AI wants to use a tool (like searching GitHub or creating a file).
                if message.tool_calls:
                    # Execute tool calls
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)

                        logger.debug(
                            f'Calling function: {function_name} with args: {function_args}'
                        )

                        # Execute the function
                        if function_name in self.tools: # Finds the tool in the agent's toolkit
                            tool_instance = self.tools[function_name]
                            # Get the method from the instance
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

                        # Serialize result properly - handle Pydantic models
                        if hasattr(result, 'model_dump'):
                            # It's a Pydantic model, use model_dump() to convert to dict
                            result_json = json.dumps(result.model_dump())
                        elif isinstance(result, dict):
                            # It's a regular dict
                            result_json = json.dumps(result)
                        else:
                            # Convert to string as fallback
                            result_json = str(result)

                        # Add tool result to conversation history(messages).
                        messages.append(
                            {
                                'role': 'tool',
                                'tool_call_id': tool_call.id,
                                'content': result_json,
                            }
                        )

                    # Send update to show we're processing
                    await task_updater.update_status(
                        TaskState.working,
                        message=task_updater.new_agent_message(
                            [TextPart(text='Processing tool calls...')]
                        ),
                    )
                    
                    # Continue the loop to get the final response
                    continue
                # No more tool calls, this is the final response, If the AI doesn't want to use any more tools, it sends the final response to the user and marks the task as complete.
                if message.content:
                    parts = [TextPart(text=message.content)]
                    logger.debug(f'Yielding final response: {parts}')
                    await task_updater.add_artifact(parts)
                    await task_updater.complete()
                break

            except Exception as e:
                logger.error(f'Error in OpenAI API call: {e}')
                error_parts = [
                    TextPart(
                        text=f'Sorry, an error occurred while processing the request: {e!s}'
                    )
                ]
                await task_updater.add_artifact(error_parts)
                await task_updater.complete()
                break

        if iteration >= max_iterations:
            error_parts = [
                TextPart(
                    text='Sorry, the request has exceeded the maximum number of iterations.'
                )
            ]
            await task_updater.add_artifact(error_parts)
            await task_updater.complete()
 

    # This method looks at a Python function and creates a description that OpenAI can understand. It's like creating a manual for each tool that tells the AI:
    # What the function does
    # What parameters it needs
    # What type each parameter should be
    # Which parameters are required
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

    # This is the main entry point that:
    # Creates a task updater to communicate with the user
    # Tells the user "I got your request and I'm starting work"
    # Extracts the text from the user's message
    # Calls the _process_request method to do the actual work
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ):
        # Run the agent until complete
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        # Immediately notify that the task is submitted.
        if not context.current_task:
            await updater.submit()
        await updater.start_work()

        # Extract text from message parts
        message_text = ''
        for part in context.message.parts:
            if isinstance(part.root, TextPart):
                message_text += part.root.text

        await self._process_request(message_text, context, updater)
        logger.debug('[GitHub Agent] execute exiting')


# This method would be used to stop the agent if needed, but it's not implemented yet (it just throws an error saying "I can't do that").
# The agent can't be stopped because it's designed to keep working until it completes the task or reaches the maximum number of iterations.
    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        # Ideally: kill any ongoing tasks.
        raise ServerError(error=UnsupportedOperationError())
