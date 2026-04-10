import re
import json
import os
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv
from utils import get_tools
from tools.base_tool import BashTool, ReadTool, EditTool, WriteTool
from tools.search_tool import GrepTool, GlobTool

# Load environment variables from .env file
load_dotenv()


class MainAgent:
    """
    Main Agent implementing ReAct (Reasoning + Acting) paradigm.

    ReAct loop: Thought -> Action -> Observation -> ... -> Final Answer
    """

    def __init__(self, max_iterations: int = 10):
        """
        Initialize the agent.

        Args:
            max_iterations: Maximum number of thought-action-observation cycles
        """
        # Initialize all tools and create name -> tool instance mapping
        self.tools: Dict[str, Any] = {}
        self._init_tools()

        # Get tool metadata for prompt
        self.tool_set = (
            get_tools.get_base_tools() +
            get_tools.get_search_tools() +
            get_tools.get_memory_tools() +
            get_tools.get_skills_tools()
        )

        # Load LLM configuration from environment variables
        self.model_name = os.getenv('MODEL_NAME', 'gpt-4')
        self.base_url = os.getenv('BASE_URL', 'https://api.openai.com/v1')
        self.api_key = os.getenv('API_KEY', '')
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', '60'))
        self.temperature = float(os.getenv('TEMPERATURE', '0.7'))
        self.max_tokens = int(os.getenv('MAX_TOKENS', '2000'))

        # ReAct configuration
        self.max_iterations = max_iterations

    def _init_tools(self):
        """Initialize all tool instances and map by name."""
        tool_instances = [
            BashTool(),
            ReadTool(),
            EditTool(),
            WriteTool(),
            GrepTool(),
            GlobTool(),
        ]

        for tool in tool_instances:
            self.tools[tool.name] = tool

    def call_llm(self, prompt: str) -> str:
        """
        Call LLM API with the given prompt.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            String response from the LLM
        """
        if not self.api_key:
            raise ValueError("API key is not configured. Please set API_KEY in .env file.")

        try:
            import requests

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }

            # Construct API endpoint
            api_endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

            response = requests.post(
                api_endpoint,
                headers=headers,
                json=payload,
                timeout=self.request_timeout
            )

            response.raise_for_status()
            result = response.json()

            # Extract the content from the response
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            else:
                raise ValueError(f"Unexpected API response format: {result}")

        except ImportError:
            raise ImportError("requests library is required. Install it with: pip install requests")
        except Exception as e:
            raise Exception(f"Failed to call LLM API: {str(e)}")

    def get_react_prompt(self, query: str, history: List[Dict[str, Any]]) -> str:
        """
        Generate the ReAct system prompt with history.

        Args:
            query: The original user query
            history: List of previous thought-action-observation cycles

        Returns:
            The complete prompt for the LLM
        """
        history_str = ""
        for i, step in enumerate(history, 1):
            history_str += f"\nStep {i}:\n"
            history_str += f"  Thought: {step.get('thought', '')}\n"
            history_str += f"  Action: {step.get('action', '')}\n"
            history_str += f"  Observation: {json.dumps(step.get('observation', {}), ensure_ascii=False)}\n"

        return f"""You are an intelligent assistant implementing the ReAct (Reasoning + Acting) paradigm.
Your goal is to answer the user's Query through iterative thinking and tool usage.

You operate in a loop of:
1. Thought: Analyze the query and previous observations to decide what to do next
2. Action: Call a tool to gather information or perform an action
3. Observation: Review the result of the action
4. Repeat until you have enough information to provide a final answer

<Query>
{query}
</Query>

<Available Tools>
{chr(10).join(self.tool_set)}
</Available Tools>

<Execution History>
{history_str if history else "(No previous actions yet)"}
</Execution History>

Now it's your turn. Based on the Query and Execution History:
- If you need more information, call a tool using the format below
- If you have enough information to answer the query, use the "finish" tool with your final answer

Strictly output the following XML tags:
<think>Your reasoning about what to do next</think>
<tool>The tool name to call (e.g., read, bash, grep, finish)</tool>
<parameter>JSON formatted parameters for the tool</parameter>"""

    def parse_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the LLM response to extract think, tool, and parameter tags.

        Returns:
            Dict with keys: think, tool, parameter
        """
        result = {
            "think": "",
            "tool": "",
            "parameter": {}
        }

        # Extract <think> content
        think_match = re.search(r'<think>(.*?)</think>', response, re.DOTALL)
        if think_match:
            result["think"] = think_match.group(1).strip()

        # Extract <tool> content
        tool_match = re.search(r'<tool>(.*?)</tool>', response, re.DOTALL)
        if tool_match:
            result["tool"] = tool_match.group(1).strip()

        # Extract <parameter> content
        param_match = re.search(r'<parameter>(.*?)</parameter>', response, re.DOTALL)
        if param_match:
            param_str = param_match.group(1).strip()
            if param_str:
                try:
                    result["parameter"] = json.loads(param_str)
                except json.JSONDecodeError:
                    result["parameter"] = param_str

        return result

    def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool by name with the given parameters.

        Args:
            tool_name: Name of the tool to call
            parameters: Dictionary of parameters to pass to the tool

        Returns:
            Dictionary with the tool execution result
        """
        if tool_name == "finish":
            # Special finish tool to end the ReAct loop
            return {
                "success": True,
                "finished": True,
                "answer": parameters.get("answer", "Task completed.")
            }

        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found. Available tools: {list(self.tools.keys())}"
            }

        tool = self.tools[tool_name]

        try:
            result = tool.run(parameters)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing tool '{tool_name}': {str(e)}"
            }

    def run(self, query: str) -> Dict[str, Any]:
        """
        Run the ReAct agent loop.

        Args:
            query: The user's query

        Returns:
            Dictionary with the final result and execution trace
        """
        history: List[Dict[str, Any]] = []
        final_answer = None

        for iteration in range(self.max_iterations):
            # Generate prompt with history
            prompt = self.get_react_prompt(query, history)

            # Call LLM
            try:
                llm_response = self.call_llm(prompt)
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "history": history,
                    "iterations": iteration
                }

            # Parse response
            parsed = self.parse_response(llm_response)

            if not parsed["tool"]:
                return {
                    "success": False,
                    "error": "No tool specified in LLM response",
                    "raw_response": llm_response,
                    "history": history,
                    "iterations": iteration + 1
                }

            # Call the tool
            tool_result = self.call_tool(parsed["tool"], parsed["parameter"])

            # Record this step
            step = {
                "iteration": iteration + 1,
                "thought": parsed["think"],
                "action": {
                    "tool": parsed["tool"],
                    "parameters": parsed["parameter"]
                },
                "observation": tool_result,
                "raw_response": llm_response
            }
            history.append(step)

            # Check if finished
            if tool_result.get("finished"):
                final_answer = tool_result.get("answer")
                break

            # Check for tool execution failure
            if not tool_result.get("success"):
                # Allow retry, record the error as observation
                pass

        # Prepare result
        result = {
            "success": final_answer is not None,
            "query": query,
            "final_answer": final_answer,
            "history": history,
            "iterations": len(history),
            "reached_max_iterations": final_answer is None and len(history) >= self.max_iterations
        }

        if result["reached_max_iterations"]:
            result["error"] = f"Reached maximum iterations ({self.max_iterations}) without final answer"

        return result

    def run_step(self, query: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run a single step of the ReAct loop (for interactive/manual control).

        Args:
            query: The user's query
            history: Previous execution history

        Returns:
            Dictionary with the step result
        """
        prompt = self.get_react_prompt(query, history)

        try:
            llm_response = self.call_llm(prompt)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "prompt": prompt
            }

        parsed = self.parse_response(llm_response)

        if not parsed["tool"]:
            return {
                "success": False,
                "error": "No tool specified",
                "raw_response": llm_response,
                "prompt": prompt
            }

        tool_result = self.call_tool(parsed["tool"], parsed["parameter"])

        return {
            "success": True,
            "thought": parsed["think"],
            "tool": parsed["tool"],
            "parameters": parsed["parameter"],
            "observation": tool_result,
            "raw_response": llm_response,
            "prompt": prompt,
            "finished": tool_result.get("finished", False),
            "answer": tool_result.get("answer") if tool_result.get("finished") else None
        }


# Example usage
if __name__ == "__main__":
    # 创建 Agent 实例
    agent = MainAgent(max_iterations=10)

    print("=" * 60)
    print("ReAct Agent 已启动！(输入 'quit' 或 'exit' 退出)")
    print("=" * 60)

    if not agent.api_key:
        print("警告: 未检测到 API_KEY。请确保在 .env 文件中配置了 API_KEY，否则调用大模型会失败。\n")

    # 进入交互式对话循环
    while True:
        try:
            query = input("\n请输入你的问题: ")

            if query.lower() in ['quit', 'exit']:
                print("退出程序。")
                break

            if not query.strip():
                continue

            print("\n" + "=" * 60)
            print(f"🎯 任务开始: {query}")
            print("-" * 60)

            history = []

            # 手动执行 ReAct 循环，以便实时打印过程
            for iteration in range(agent.max_iterations):
                print(f"\n[第 {iteration + 1} 步] 大模型正在思考...")

                # 调用单步执行
                step_result = agent.run_step(query, history)

                if not step_result.get("success"):
                    print(f"❌ 运行报错: {step_result.get('error')}")
                    print(f"原始响应: {step_result.get('raw_response', '无')}")
                    break

                # ====== 外显核心内容 ======
                print(f"💡 思考 (Think): {step_result.get('thought')}")
                print(f"🔧 工具 (Tool): {step_result.get('tool')}")
                print(f"📦 参数 (Params): {step_result.get('parameters')}")

                observation = step_result.get('observation', {})

                # 为了防止控制台被大量内容刷屏，稍微截断一下过长的观察结果
                obs_str = str(observation)
                if len(obs_str) > 300:
                    obs_str = obs_str[:300] + "... [内容过长已截断]"
                print(f"👁️ 观察 (Observation): {obs_str}")

                # 将当前步骤加入历史记录，供下一步大模型参考
                history.append({
                    "thought": step_result.get('thought'),
                    "action": {
                        "tool": step_result.get('tool'),
                        "parameters": step_result.get('parameters')
                    },
                    "observation": observation
                })

                # 检查是否调用了 finish 工具，任务结束
                if step_result.get("finished"):
                    print("\n" + "=" * 60)
                    print("✨ 最终答案:")
                    print(step_result.get("answer"))
                    print("=" * 60)
                    break

            else:
                # 触发了 for-else 逻辑，说明跑满了 max_iterations 还是没拿到结果
                print("\n⚠️ 达到最大迭代次数，大模型未能给出最终答案。")

        except KeyboardInterrupt:
            print("\n程序已被强制中断。")
            break
        except Exception as e:
            print(f"\n发生意外错误: {e}")