"""Small agent with explicit responsibilities; a starting point for M03+ agents."""
from core.llm.client import generate

SYSTEM_PROMPT = "你是投资研究助手。当前仅进行一般对话测试；不得假装已经阅读BP，不得编造来源。对无法核实的信息明确说明。"

def run_demo_agent(question: str) -> dict:
    result = generate(question, SYSTEM_PROMPT)
    return {"agent": "general_research_demo", **result}
