"""APIGenMT tool injection prompt templates.

Ported from bannff/Agentic-Datasets@26cb683 (``llm/prompts/apigenmt.py``).
"""

APIGENMT_SYSTEM = """You are an expert at enhancing conversations with tool calls.

Your task is to identify where tool calls would add value to a conversation
and inject them naturally following the APIGen methodology.

Guidelines:
- Only inject tools that genuinely help answer the user's question
- Tool calls should feel natural, not forced
- Extract realistic parameters from conversation context
- Add 1-3 tool calls per conversation maximum"""


APIGENMT_ANALYZE = """Analyze this conversation and determine which tools would be helpful.

Conversation:
{conversation}

Available Tools:
{tools}

For each potential tool call, provide:
1. Which message to inject it after
2. Why it's relevant
3. What parameters to extract from context

Return a JSON object:
{{
  "tool_calls": [
    {{
      "after_message_index": 0,
      "tool_name": "...",
      "reasoning": "...",
      "arguments": {{"param": "value"}}
    }}
  ]
}}

If no tools are appropriate, return: {{"tool_calls": []}}

Return ONLY the JSON, no other text."""


APIGENMT_GENERATE_RESPONSE = """Generate a realistic tool response.

Tool: {tool_name}
Arguments: {arguments}
Tool Description: {description}

Generate a realistic, helpful response that this tool would return.
The response should be informative and relevant to the arguments provided.

Return ONLY the tool response content, no other text."""
