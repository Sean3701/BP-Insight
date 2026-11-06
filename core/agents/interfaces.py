from dataclasses import dataclass, field
from typing import Protocol

@dataclass
class AgentTask:
    task_id: str
    project_id: int
    instruction: str
    evidence_ids: list[str] = field(default_factory=list)

@dataclass
class AgentResult:
    task_id: str
    agent_name: str
    output: str
    evidence_ids: list[str] = field(default_factory=list)

class Agent(Protocol):
    def run(self, task: AgentTask) -> AgentResult:
        ...
