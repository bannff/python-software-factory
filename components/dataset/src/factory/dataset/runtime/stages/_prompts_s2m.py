"""S2M (Single-to-Multi turn) transformation prompt templates.

Ported from bannff/Agentic-Datasets@26cb683 (``llm/prompts/s2m.py``).
"""

S2M_SYSTEM = """You are an expert conversation generator.

Your task is to transform single-turn Q&A pairs into natural, coherent 
multi-turn conversations that feel like real dialogue.

Guidelines:
- Start with the original question
- Generate natural follow-up questions that explore deeper
- Each response should build on previous context
- Aim for 3-5 total turns
- End when the topic is thoroughly covered"""


S2M_TRANSFORM = """Transform this single-turn Q&A into a multi-turn conversation.

Original Question: {question}
Original Answer: {answer}

Generate a natural conversation with 3-5 turns where:
1. First turn uses the original question and answer
2. Follow-up questions dig deeper or ask for examples
3. Each response references prior context
4. Conversation flows naturally

Return a JSON array of messages:
[
  {{"role": "user", "content": "..."}},
  {{"role": "assistant", "content": "..."}},
  ...
]

Return ONLY the JSON array, no other text."""
