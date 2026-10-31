"""Model constants for swarm ensemble diversity.

Tested model families with tool-calling support (2026-04-12):
- HAIKU: Fast, reliable, clean tool params. Primary workhorse.
- SONNET: Sonnet 4.6 — frontier coding/agents at mid-tier cost.
  Best SAST scanner (96.25%), consolidator (96.7%), hierarchy-analyzer (96.7%).
  Too adversarial for validator role (20%).
- GLM5: Z.AI GLM 5 — 745B MoE, frontier agentic model.
  Best validator (100%), best DAST IDOR (90%). Weaker on SAST scanning (66.7%).
- NOVA2_LITE: Cheap, low false positive rate. Content filters block DAST/pentest.
  Best as validator (100%) or cheap SAST consensus vote. NOT for DAST.
- GPT_OSS: OpenAI 120B open-weight. Clean params, has reasoning/CoT.
  Inconsistent execution (50% SAST) but good methodology. Diversity vote.
- SCOUT: Llama 4 MoE (16 experts), 10M context. Weak on verification (56.7%).
- MAVERICK: Llama 4 MoE (128 experts), 400B params. Needs normalizer.
- HAIKU: Best at reporting (100%), deployment (90.8%), recon (91.9%).
  Refuses some pentest recon tasks.

Not working: DeepSeek-R1 (no tool use), Nova 1 Lite (content filters).

ENSEMBLE is the full set — every swarm should include all of these.
"""

HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
SONNET = "us.anthropic.claude-sonnet-4-6"
GLM5 = "zai.glm-5"
NOVA2_LITE = "us.amazon.nova-2-lite-v1:0"
SCOUT = "us.meta.llama4-scout-17b-instruct-v1:0"
MAVERICK = "us.meta.llama4-maverick-17b-instruct-v1:0"
GPT_OSS = "openai.gpt-oss-120b-1:0"

# OpenAI frontier models on Amazon Bedrock — Responses API ONLY, served via
# the bedrock-mantle endpoint (resolved by strands_adapter._build_mantle_model,
# NOT Converse). Region-gated as of 2026-06: gpt-5.5 → us-east-2 (Ohio) only;
# gpt-5.4 → us-east-2 + us-west-2 (Oregon) + GovCloud (US-West). Set the mantle
# region via BEDROCK_MANTLE_REGION (default us-east-2). NOT in ENSEMBLE — these
# require separate model access enablement and a region with the model present.
GPT55 = "openai.gpt-5.5"
GPT54 = "openai.gpt-5.4"

ENSEMBLE = [HAIKU, SONNET, GLM5, NOVA2_LITE, SCOUT, MAVERICK, GPT_OSS]
