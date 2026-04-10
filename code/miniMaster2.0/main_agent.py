import os
import json
import re
from dotenv import load_dotenv
from openai import OpenAI
from tqdm.asyncio import tqdm_asyncio

# 导入工具类
from tools.base_tool import BashTool, ReadTool, EditTool, WriteTool
from tools.search_tool import GrepTool, GlobTool

# 导入工具注册表
from utils.get_tools import get_registry, execute_tool


class ToDoList:
    """待办事项列表管理类"""

    def __init__(self):
        self.tasks = []

    def add_task(self, task_name: str, task_status: str = "PENDING", task_conclusion: str = ""):
        self.tasks.append({
            "task_name": task_name,
            "task_status": task_status,
            "task_conclusion": task_conclusion
        })

    def init_tasks(self, task_list: list):
        for item in task_list:
            if isinstance(item, str):
                self.add_task(item)
            elif isinstance(item, dict):
                self.add_task(item.get("task_name", ""), item.get("task_status", "PENDING"),
                              item.get("task_conclusion", ""))

    def update_task_status(self, task_name: str, new_status: str) -> bool:
        for task in self.tasks:
            if task["task_name"] == task_name:
                task["task_status"] = new_status
                return True
        return False

    def update_task_conclusion(self, task_name: str, conclusion: str) -> bool:
        for task in self.tasks:
            if task["task_name"] == task_name:
                task["task_conclusion"] = conclusion
                return True
        return False

    def get_all_tasks(self):
        return self.tasks.copy()

    def get_task_by_name(self, task_name: str):
        for task in self.tasks:
            if task["task_name"] == task_name:
                return task
        return None


class WorkingMemory:
    """工作记忆管理类 - 记录agent短时记忆"""

    def __init__(self):
        self.memories = []

    def add_memory(self, step: int, tool_name: str, parameters: dict, result: any):
        self.memories.append({
            "step": step,
            "tool_call": {"tool_name": tool_name, "parameters": parameters},
            "result": result
        })

    def get_memory_by_step(self, step: int):
        for memory in self.memories:
            if memory["step"] == step:
                return memory.copy()
        return None

    def get_all_memories(self):
        return self.memories.copy()

    def clear_memories(self):
        self.memories = []


# ==========================================
# 辅助函数
# ==========================================
def parse_model_output(response_text: str):
    """
    解析模型输出的 <think>, <tool>, <parameter> 标签
    返回: tool_name, parameters_dict
    """
    # 提取 <think> 标签内容（可选，用于调试）
    think_match = re.search(r'<think>(.*?)</think>', response_text, re.DOTALL)
    think_content = think_match.group(1).strip() if think_match else ""

    # 提取 <tool> 标签内容
    tool_match = re.search(r'<tool>(.*?)</tool>', response_text, re.DOTALL)
    tool_name = tool_match.group(1).strip() if tool_match else ""

    # 提取 <parameter> 标签内容
    param_match = re.search(r'<parameter>(.*?)</parameter>', response_text, re.DOTALL)
    param_content = param_match.group(1).strip() if param_match else ""

    # 解析参数为 dict
    parameters = {}
    if param_content:
        try:
            parameters = json.loads(param_content)
        except json.JSONDecodeError:
            # 如果不是合法 JSON，作为字符串处理
            parameters = {"raw": param_content}

    return tool_name, parameters


# 工具实例缓存
tool_instances = {}

def get_tool_instance(tool_class):
    """获取工具实例（单例模式）"""
    class_name = tool_class.__name__
    if class_name not in tool_instances:
        tool_instances[class_name] = tool_class()
    return tool_instances[class_name]

# 初始化工具注册表（全局单例）
tool_registry = get_registry()


def execute_tool(tool_name: str, parameters: dict):
    """
    执行对应的工具逻辑
    使用 ToolRegistry 动态路由到对应的工具并执行
    """
    # 待办事项相关工具（在代码中直接处理）
    todo_tools = ["init_tasks", "add_task", "update_task_status"]

    if tool_name in todo_tools:
        # 这些工具在 Plan-Agent 循环中直接处理，不需要执行外部工具
        return {"success": True, "message": f"Todo tool '{tool_name}' should be handled directly"}

    # 使用工具注册表执行工具
    return tool_registry.execute(tool_name, parameters)


# ==========================================
# 主体逻辑
# ==========================================
if __name__ == "__main__":
    load_dotenv()

    # 从环境变量读取配置（与 .env 文件保持一致）
    API_KEY = os.environ.get("API_KEY")
    BASE_URL = os.environ.get("BASE_URL")
    MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-chat")

    # 检查必需的环境变量
    if not API_KEY:
        print("错误: 未设置 API_KEY 环境变量")
        print("请在 .env 文件中设置: API_KEY=your_api_key_here")
        exit(1)

    if not BASE_URL:
        print("错误: 未设置 BASE_URL 环境变量")
        print("请在 .env 文件中设置: BASE_URL=https://api.example.com")
        exit(1)

    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
    )

    # 获取用户输入的查询
    user_query = input("请输入你的任务/查询: ").strip()
    if not user_query:
        print("查询不能为空，退出程序。")
        exit(1)

    to_do_list = ToDoList()
    generator_memory = WorkingMemory()
    validation_memory = WorkingMemory()
    max_iter = 30

    # 🟢 第一层循环：Plan-Agent (任务规划与调度)
    for i in range(max_iter):
        print(f"\n{'='*60}")
        print(f"🔄 Plan-Agent 第 {i+1} 次迭代")
        print(f"{'='*60}")

        # 1. 组装 Plan-Agent Prompt
        plan_prompt = f"""
你是一个规划智能体，你的任务是根据用户的 query 维护和调度当前工作状态。

<user query>
{user_query}
</user query>

<to do list>
{to_do_list.get_all_tasks()}
</to do list>

<available tools>
- init_tasks: 初始化任务列表，一次性添加多个任务
  Input schema: {{"type": "object", "properties": {{"tasks": {{"type": "array", "items": {{"type": "string"}}}}}}, "required": ["tasks"]}}

- add_task: 添加单个任务
  Input schema: {{"type": "object", "properties": {{"task_name": {{"type": "string"}}}}, "required": ["task_name"]}}

- update_task_status: 更新任务状态
  Input schema: {{"type": "object", "properties": {{"task_name": {{"type": "string"}}, "status": {{"type": "string", "enum": ["PENDING", "DONE", "FAILED"]}}}}, "required": ["task_name", "status"]}}

- subagent_tool: 创建子智能体执行具体任务（分配到具体执行者）
  Input schema: {{"type": "object", "properties": {{"task_name": {{"type": "string", "description": "要执行的任务名称"}}}}, "required": ["task_name"]}}
</available tools>

<instructions>
1. 分析用户查询和当前任务列表
2. 选择合适的工具来管理任务
3. init_tasks 用于初始化，add_task 用于添加单个任务
4. subagent_tool 用于将任务分配给执行智能体
</instructions>

<output format>
    <think>你的思考内容：分析当前状态，选择合适工具</think>
    <tool>你要使用的工具名称</tool>
    <parameter>{{"参数名": "参数值"}}  <!-- 工具参数，JSON格式 --></parameter>
</output format>
"""

        plan_response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": plan_prompt}]
        )

        plan_tool, plan_params = parse_model_output(plan_response.choices[0].message.content)
        print(f"📋 Plan-Agent 选择工具: {plan_tool}")
        print(f"📋 Plan-Agent 参数: {plan_params}")

        # 2. Plan-Agent 工具路由
        if plan_tool == "init_tasks":
            # 初始化任务列表
            task_list = plan_params.get("tasks", [])
            to_do_list.init_tasks(task_list)
            print(f"✅ 已初始化任务列表: {task_list}")
            continue

        elif plan_tool == "add_task":
            # 添加单个任务
            task_name = plan_params.get("task_name", "")
            if task_name:
                to_do_list.add_task(task_name)
                print(f"✅ 已添加任务: {task_name}")
            continue

        elif plan_tool == "update_task_status":
            # 更新任务状态
            task_name = plan_params.get("task_name", "")
            new_status = plan_params.get("status", "PENDING")
            if task_name:
                to_do_list.update_task_status(task_name, new_status)
                print(f"✅ 已更新任务 '{task_name}' 状态为: {new_status}")
            continue

        elif plan_tool == "subagent_tool":
            curr_task_name = plan_params.get("task_name")
            curr_task = to_do_list.get_task_by_name(curr_task_name)

            if not curr_task:
                print(f"⚠️  未找到任务: {curr_task_name}")
                continue

            print(f"\n🚀 开始执行任务: {curr_task_name}")
            print(f"📝 任务详情: {curr_task}")

            # 🟡 第二层循环：Generator (任务执行与生成)
            generator_memory.clear_memories()
            gen_step = 0

            while True:
                gen_step += 1
                print(f"\n  🔧 Generator 第 {gen_step} 步")

                # 获取工具描述（动态生成）
                base_tools = tool_registry.get_all_tools_prompt(category="base_tool")
                search_tools = tool_registry.get_all_tools_prompt(category="search_tool")

                generator_prompt = f"""
你是一个生成智能体，你的任务是执行具体任务并生成内容。

<user query>
{user_query}
</user query>

<current task>
{curr_task}
</current task>

<working memory>
{generator_memory.get_all_memories()}
</working memory>

<available tools>
【基础工具】
{base_tools}

【搜索工具】
{search_tools}

【任务管理】
- update_task_conclusion: 任务完成时调用，传入参数为任务完成的结论
  Input schema: {{"type": "object", "properties": {{"conclusion": {{"type": "string"}}}}, "required": ["conclusion"]}}
</available tools>

<instructions>
1. 仔细分析当前任务和用户查询
2. 选择合适的工具来帮助你完成任务
3. 按照 output format 格式输出
4. 如果需要调用工具，parameter 必须是合法的 JSON 格式
</instructions>

<output format>
    <think>你的思考内容：分析任务，选择合适的工具，解释为什么</think>
    <tool>你要使用的工具名称（从 available tools 中选择）</tool>
    <parameter>{{"参数名": "参数值"}}  <!-- 工具需要的参数，JSON格式 --></parameter>
</output format>
"""

                gen_response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": generator_prompt}]
                )

                gen_tool, gen_params = parse_model_output(gen_response.choices[0].message.content)
                print(f"  🛠️  Generator 选择工具: {gen_tool}")
                print(f"  🛠️  参数: {gen_params}")

                if gen_tool != "update_task_conclusion":
                    # 执行普通工具并记录到 Generator 记忆
                    result = execute_tool(gen_tool, gen_params)
                    generator_memory.add_memory(gen_step, gen_tool, gen_params, result)
                    print(f"  ✅ 工具执行结果: {result}")
                    continue  # 继续第二层循环，Generator 继续工作

                else:
                    # Generator 认为完成了，更新结论
                    conclusion = gen_params.get("conclusion", "")
                    to_do_list.update_task_conclusion(curr_task_name, conclusion)
                    print(f"  📝 Generator 完成任务，结论: {conclusion}")

                    # 🔴 第三层循环：Validate-Agent (结果测试与验证)
                    validation_memory.clear_memories()
                    val_step = 0
                    is_valid = False

                    while True:
                        val_step += 1
                        print(f"\n    🔍 Validate-Agent 第 {val_step} 步")
                        # 注意：需要重新获取 task，因为结论刚刚更新了
                        updated_task = to_do_list.get_task_by_name(curr_task_name)

                        # 获取工具描述
                        base_tools = tool_registry.get_all_tools_prompt(category="base_tool")
                        search_tools = tool_registry.get_all_tools_prompt(category="search_tool")

                        val_prompt = f"""你是一个测试验证智能体，你的任务是验证工作是否有效。

<task>
{updated_task}
</task>

<working memory>
{validation_memory.get_all_memories()}
</working memory>

<available tools>
【基础工具】
{base_tools}

【搜索工具】
{search_tools}

【验证工具】
- validate_tool: 验证任务完成是否有效
  Input schema: {{"type": "object", "properties": {{"status": {{"type": "string", "enum": ["有效", "无效"]}}, "reason": {{"type": "string"}}}}, "required": ["status"]}}
</available tools>

<instructions>
1. 分析任务和完成结论
2. 使用工具（如 read, grep 等）验证结论是否正确
3. 最后调用 validate_tool 给出验证结果（"有效" 或 "无效"）
4. 如果无效，提供详细原因
</instructions>

<output format>
    <think>你的思考内容</think>
    <tool>你要使用的工具名称</tool>
    <parameter>{{"参数名": "参数值"}}</parameter>
</output format>
"""

                        val_response = client.chat.completions.create(
                            model=MODEL_NAME,
                            messages=[{"role": "user", "content": val_prompt}]
                        )

                        val_tool, val_params = parse_model_output(val_response.choices[0].message.content)
                        print(f"    🛠️  Validate-Agent 选择工具: {val_tool}")
                        print(f"    🛠️  参数: {val_params}")

                        if val_tool != "validate_tool":
                            # 执行验证辅助工具（如搜索、基础测试等）
                            val_result = execute_tool(val_tool, val_params)
                            validation_memory.add_memory(val_step, val_tool, val_params, val_result)
                            print(f"    ✅ 验证工具执行结果: {val_result}")
                            continue  # 继续第三层循环，直到得出最终验证结果

                        else:
                            # 验证器得出最终结论
                            status = val_params.get("status")  # 假设参数为 "有效" 或 "无效"
                            reason = val_params.get("reason", "未知错误")
                            print(f"    📊 验证结果: {status}, 原因: {reason}")

                            if status == "有效":
                                is_valid = True
                                print(f"    ✅ 验证通过！")
                                break  # 结束第三层循环
                            else:
                                # 验证失败：将错误原因写入 Generator 的记忆中，让其重试
                                generator_memory.add_memory(
                                    gen_step + 1,
                                    "system_feedback",
                                    {},
                                    f"验证失败，请重新调整。原因: {reason}"
                                )
                                is_valid = False
                                print(f"    ❌ 验证失败，将返回 Generator 重试")
                                break  # 结束第三层循环，回到第二层循环 (Generator)

                    # 🔴 第三层循环结束后的处理
                    if is_valid:
                        # 验证通过，更新任务状态为完成，清空记忆
                        to_do_list.update_task_status(curr_task_name, "DONE")
                        generator_memory.clear_memories()
                        validation_memory.clear_memories()
                        print(f"\n✅ 任务 '{curr_task_name}' 已完成并通过验证！")
                        break  # 结束第二层循环，回到第一层循环 (Plan-Agent)
                    else:
                        # 验证未通过，继续第二层循环 (Generator 继续基于新的 feedback 工作)
                        print(f"\n⚠️  任务 '{curr_task_name}' 验证未通过，Generator 将继续重试...")
                        continue

        else:
            # 未知工具，跳过
            continue

        # 检查是否所有任务都已完成
        all_tasks = to_do_list.get_all_tasks()
        if all_tasks and all(task["task_status"] == "DONE" for task in all_tasks):
            print("\n=== 所有任务已完成 ===")
            for task in all_tasks:
                print(f"任务: {task['task_name']}")
                print(f"结论: {task['task_conclusion']}")
            break

    print("\n程序结束。")