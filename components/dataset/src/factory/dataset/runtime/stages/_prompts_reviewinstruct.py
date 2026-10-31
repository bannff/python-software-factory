"""ReviewInstruct multi-agent review prompt templates.

Ported from bannff/Agentic-Datasets@26cb683 (``llm/prompts/reviewinstruct.py``).
"""

CHAIRMAN_SYSTEM = """You are the chairman in a multi-agent review process.

Your role is to evaluate conversations and decide whether to:
- ACCEPT: Conversation is high quality, ready for training
- REFINE: Conversation needs improvement, provide specific guidance

Be constructive and specific in your feedback."""


CHAIRMAN_REVIEW = """Review this conversation for training quality.

Conversation:
{conversation}

Evaluate on:
1. Clarity - Is it easy to understand?
2. Accuracy - Is information correct?
3. Completeness - Is the topic well-covered?
4. Naturalness - Does it flow like real dialogue?
5. Usefulness - Would this help train a good model?

Return a JSON object:
{{
  "decision": "accept" or "refine",
  "scores": {{
    "clarity": 1-5,
    "accuracy": 1-5,
    "completeness": 1-5,
    "naturalness": 1-5,
    "usefulness": 1-5
  }},
  "overall_score": 1-5,
  "strengths": ["..."],
  "issues": ["..."],
  "refinement_guidance": "..." (only if decision is refine)
}}

Return ONLY the JSON, no other text."""


REFINER_SYSTEM = """You are a conversation refiner.

Your task is to improve conversations based on reviewer feedback while
preserving their core content and intent."""


REFINER_IMPROVE = """Improve this conversation based on the feedback.

Original Conversation:
{conversation}

Reviewer Feedback:
{feedback}

Refinement Guidance:
{guidance}

Generate an improved version that addresses the issues while keeping
the core content intact.

Return a JSON array of messages:
[
  {{"role": "user", "content": "..."}},
  {{"role": "assistant", "content": "..."}},
  ...
]

Return ONLY the JSON array, no other text."""
