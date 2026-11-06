import os
import unittest
from unittest.mock import patch
from core.llm.client import generate, ModelError
from core.agents.demo import run_demo_agent

class TestM02(unittest.TestCase):
    def test_mock(self):
        with patch.dict(os.environ, {"VC_LLM_PROVIDER": "mock"}):
            value=run_demo_agent("你好")
            self.assertIn("模拟结果", value["answer"])
            self.assertEqual(value["agent"], "general_research_demo")
    def test_invalid_provider(self):
        with patch.dict(os.environ, {"VC_LLM_PROVIDER": "invalid"}):
            with self.assertRaises(ModelError):
                generate("test")

if __name__ == '__main__':
    unittest.main()
