"""AgentInstruct transformation prompt templates.

Ported from bannff/Agentic-Datasets@26cb683 (``llm/prompts/agentinstruct.py``).
Based on the Microsoft AgentInstruct methodology.
"""

AGENTINSTRUCT_SYSTEM = """You are an expert instruction transformer following the AgentInstruct methodology.

Your task is to transform a seed instruction into diverse, high-quality variants that:
1. Maintain the core intent and domain focus
2. Vary in complexity, format, and approach
3. Are self-contained and actionable
4. Cover different aspects or perspectives of the topic

Each variant should feel natural and could be asked by a real user."""


TRANSFORM_QA = """Transform this instruction into a Question-Answering format.
The result should be a clear, focused question that expects a factual or explanatory answer.

Seed instruction: {seed}

Generate a Q&A style variant that:
- Asks for specific information or explanation
- Is precise and unambiguous
- Can be answered with facts, steps, or clear explanations

Return ONLY the transformed instruction, nothing else."""


TRANSFORM_OPEN_WRITING = """Transform this instruction into an open-domain writing task.
The result should encourage creative or comprehensive exploration.

Seed instruction: {seed}

Generate a writing-focused variant that:
- Invites detailed explanation or exploration
- Allows for examples and illustrations
- Encourages thorough coverage of the topic

Return ONLY the transformed instruction, nothing else."""


TRANSFORM_CODING = """Transform this instruction into a coding/technical implementation focus.
The result should request code, debugging, or technical implementation.

Seed instruction: {seed}

Generate a code-focused variant that:
- Asks for code examples or implementation
- Requests debugging or troubleshooting steps
- Focuses on practical, executable solutions

Return ONLY the transformed instruction, nothing else."""


TRANSFORM_CLASSIFICATION = """Transform this instruction into a classification or categorization task.
The result should ask for organizing, categorizing, or comparing items.

Seed instruction: {seed}

Generate a classification variant that:
- Asks for categorization or taxonomy
- Requests comparison between alternatives
- Focuses on organizing or structuring information

Return ONLY the transformed instruction, nothing else."""


TRANSFORM_SUMMARIZATION = """Transform this instruction into a summarization request.
The result should ask for concise, key-point extraction.

Seed instruction: {seed}

Generate a summarization variant that:
- Requests concise overview or summary
- Asks for key points or takeaways
- Focuses on distilling essential information

Return ONLY the transformed instruction, nothing else."""


TRANSFORM_EXTRACTION = """Transform this instruction into an information extraction task.
The result should ask for pulling specific data or patterns.

Seed instruction: {seed}

Generate an extraction variant that:
- Asks for specific data points or facts
- Requests identification of patterns or elements
- Focuses on extracting structured information

Return ONLY the transformed instruction, nothing else."""


TRANSFORM_REASONING = """Transform this instruction into a multi-step reasoning task.
The result should require logical thinking and step-by-step analysis.

Seed instruction: {seed}

Generate a reasoning variant that:
- Requires step-by-step logical analysis
- Asks for justification or explanation of conclusions
- Involves evaluating trade-offs or making decisions

Return ONLY the transformed instruction, nothing else."""


TRANSFORM_PROMPTS = {
    "qa": TRANSFORM_QA,
    "writing": TRANSFORM_OPEN_WRITING,
    "coding": TRANSFORM_CODING,
    "classification": TRANSFORM_CLASSIFICATION,
    "summarization": TRANSFORM_SUMMARIZATION,
    "extraction": TRANSFORM_EXTRACTION,
    "reasoning": TRANSFORM_REASONING,
}


COMPLEXITY_SYSTEM = """You are an expert at adjusting instruction complexity.

Adjust the given instruction to the specified difficulty level while
maintaining its core meaning and intent."""


COMPLEXITY_BEGINNER = """Simplify this instruction for a beginner audience.

Original: {instruction}

Create a beginner-friendly version that:
- Uses simpler language
- Asks for basic explanations
- Focuses on fundamentals

Return ONLY the simplified instruction, nothing else."""


COMPLEXITY_INTERMEDIATE = """Adjust this instruction for an intermediate audience.

Original: {instruction}

Create an intermediate version that:
- Assumes some background knowledge
- Asks for more detailed explanations
- Includes practical applications

Return ONLY the adjusted instruction, nothing else."""


COMPLEXITY_ADVANCED = """Enhance this instruction for an advanced audience.

Original: {instruction}

Create an advanced version that:
- Assumes expert knowledge
- Asks for edge cases and nuances
- Focuses on optimization or best practices

Return ONLY the enhanced instruction, nothing else."""


COMPLEXITY_PROMPTS = {
    "beginner": COMPLEXITY_BEGINNER,
    "intermediate": COMPLEXITY_INTERMEDIATE,
    "advanced": COMPLEXITY_ADVANCED,
}
