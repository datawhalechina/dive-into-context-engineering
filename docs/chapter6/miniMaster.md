# miniMaster

本项目是一个极简的实例，着重实现维护agent长期运行稳定的方法，快速体验harness的核心理念

## 1. Tool 设计

### 1.1 基础系统工具 (Base Tools)

`base_tool` 目录提供 Agent 与系统交互的基础能力：

* **Bash Tool**：执行 Shell 命令，支持超时控制（默认 30s），返回结构化结果。
* **Read Tool**：读取文件内容，支持按行号范围读取。
* **Write Tool**：写入文件，支持覆盖、追加、新建三种模式，自动创建目录。
* **Edit Tool**：精准修改代码，支持文本替换和全局替换选项。

### 1.2 搜索检索工具 (Search Tools)

`search_tool` 目录提供文件和文本检索能力：

* **Glob Tool**：基于通配符查找文件，支持递归搜索和隐藏文件过滤。
* **Grep Tool**：基于正则表达式搜索文本，支持大小写区分、递归遍历和文件类型过滤。

### 1.3 工具核心层 (Tool Core)

`tools/core/` 是工具系统的管理框架，负责统一发现、创建、执行和描述工具。具体工具只需关注业务逻辑，公共问题（参数校验、实例复用、结果归一化等）由核心层处理。

* **BaseTool**：所有工具的基类，负责参数校验、结果归一化和 Prompt 导出。
* **ToolSpec / ToolContext / ToolResult**：分别定义工具元信息、运行时上下文和执行结果格式。
* **ToolCatalog & discover_tools**：维护工具注册表，自动扫描并注册新工具。
* **ToolFactory & ToolExecutor**：负责工具实例创建（支持单例策略）和统一执行入口。
* **ToolPromptRenderer & ToolService**：生成模型可读的工具说明，提供对外统一服务接口。

这种分层设计使新增工具时无需重复实现校验、注册、错误处理等通用逻辑，提升可维护性。

### 1.4 统一的接口设计

所有工具遵循一致的接口规范：

* **结构化元信息**：通过 `ToolSpec` 声明工具名称、说明、分类和输入 schema。
* **标准化执行流程**：业务逻辑封装在 `run()` 方法中，统一通过 `execute()` 调用。
* **统一结果结构**：返回包含 `success`、数据和错误信息的字典，确保容错性。
* **统一服务入口**：通过 `utils/get_tools.py` 提供 `get_registry()`、`execute_tool()` 等接口。
* **控制指令分流**：任务调度指令（如 `init_tasks`）与真实工具调用（如 `read`、`bash`）分离，保持逻辑清晰。


---

## 2. 状态管理与动态工作记忆 (State Management)

在harness的设计中,状态和记忆管理十分重要,让agent知道各个任务的状态和它自己曾经采取过什么样的行动,从而使它更好的做出有下一步决策
任何一个需要持续工作的 Agent,都面临一个核心的技术挑战:**如何平衡不断增长的执行记录与 LLM 有限的上下文窗口(Token 限制)?** 如果像"金鱼"一样只有短暂记忆,Agent 就会陷入死循环;但如果把所有历史都毫无保留地塞进 Prompt,不仅会导致 Token 溢出报错,还会让大模型产生"幻觉"或"分心"(Lost in the Middle)。

为了解决这个问题,在架构中,状态管理被清晰地划分为"宏观"和"微观"两层。宏观层面由 `ToDoList` 类接管,充当 Agent 的"任务看板",记录全局子任务的生命周期。而微观层面,也就是 Agent 执行具体动作时的"脑容量",则交由 **`WorkingMemory`(动态压缩工作记忆)** 来管理。

不采用简单的"丢弃最旧记忆"的滑动窗口策略,而是实现了一套**基于字符长度触发的平滑动态压缩机制**。下面是核心代码实现:

```python
import json

class WorkingMemory:
    """工作记忆管理类 - 按照 Token(字符) 长度触发动态压缩"""

    def __init__(self, keep_latest_n: int = 3, max_chars: int = 45000):
        self.memories = []
        # 触发压缩时，保留最后几个步骤的完整 JSON 不被压缩（保持当前工作的连贯性）

        self.keep_latest_n = keep_latest_n
        # 触发阈值：20k token 大约等于 40000~50000 个字符

        self.max_chars = max_chars
        self.summary = ""

    def add_memory(self, step: int, tool_name: str, parameters: dict, result: any):
        """添加新记忆（记录每一步的工具调用和返回结果）"""
        self.memories.append({
            "step": step,
            "tool_call": {"tool_name": tool_name, "parameters": parameters},
            "result": result
        })

    def get_prompt_context(self) -> str:
        """组装给 Agent 看的完整上下文：早期摘要 + 近期详细步骤"""
        context = ""
        if self.summary:
            context += f"【早期步骤摘要】:\n{self.summary}\n\n"

        # 只要没超限，Agent 就能看到所有近期步骤的完整内容

        context += "【执行步骤】:\n" + json.dumps(self.memories, ensure_ascii=False, indent=2)
        return context

    def check_needs_summary(self) -> bool:
        """核心策略：判断当前上下文是否超过了容量阈值"""
        current_length = len(self.get_prompt_context())
        # 只有长度超标，且记忆数量大于我们要保留的底线时，才触发压缩

        return current_length > self.max_chars and len(self.memories) > self.keep_latest_n

    def get_memories_to_summarize(self) -> list:
        """获取需要被压缩的庞大旧记忆"""
        if self.check_needs_summary():
            # 取出除了最后 keep_latest_n 步之外的所有早期记忆，打包准备送去压缩

            return self.memories[:-self.keep_latest_n]
        return []

    def commit_summary(self, new_summary: str):
        """用大模型返回的摘要覆盖旧摘要，并清理掉已被压缩的冗长数据"""
        self.summary = new_summary
        # 核心：截断数组，只保留最后 keep_latest_n 步的详细记忆，腾出大量空间

        self.memories = self.memories[-self.keep_latest_n:]
```

### 2.1 动态记忆压缩是如何运转的?

1. **内容长度检测 (`check_needs_summary`)**
   通过 `max_chars`（默认约 4.5 万字符，大致对应 20k Tokens）设定了安全红线。每一次执行新动作前，系统都会预检当前的上下文长度。只有当文本量真正逼近 Token 极限时，才会触发压缩动作。这意味着在资源允许的范围内，Agent 始终拥有最高精度、最完整的上下文。
2. **平滑的上下文过渡 (`keep_latest_n`)**
   通过切片操作 `self.memories[:-self.keep_latest_n]` 和 `self.memories[-self.keep_latest_n:]`，我在触发压缩时，**强制保留了最近 N 步（如 3 步或 8 步）的完整 JSON 记录**。这保证了 Agent 思考和执行的微观连贯性。
3. **滚动式记忆沉淀 (`get_prompt_context` & `commit_summary`)**
   当触发压缩时，被抛弃的早期记录并没有消失。主循环（参考后续的 `Generator-Agent` 逻辑）会调用大模型，将这些冗长的早期 JSON 记录连同旧的 `summary` 一起，浓缩成一段高度精简的文本。在下一次拼接 Prompt 时，Agent 看到的将会是：`【早期步骤摘要】+【最近 3 步详细 JSON 执行过程】`。

---

## 3. 多智能体编排 (multi-agent Orchestration)

**"规划-执行-验证"三层嵌套循环 (Plan-Generate-Validate)** 的多智能体协作架构。各agent均遵循React范式。相对于plan & slove的方式,增加了validate,每次完成任务先进行校验,校验通过后,才进入下一层。以保证在长期任务中的稳定性
每个 Agent 各司其职,拥有独立的 Prompt 和职责边界:

### 3.1 Plan-Agent (全局调度)

Plan-Agent 是整个系统的大脑。它不直接干脏活累活（比如写代码或查文件），它的唯一职责是审视用户的原始需求，并维护 `ToDoList` 任务看板。

它的核心循环受 `max_iter` 控制，通过专属的任务管理工具（如 `init_tasks`, `add_task`）来拆解步骤。当它明确了当前要做的具体任务后，会调用 `subagent_tool`，将任务“外包”给下层的执行智能体：

```python
        # 伪代码：Plan-Agent 的核心路由逻辑

        if plan_tool == "init_tasks":
            to_do_list.init_tasks(task_list)
            continue
        elif plan_tool == "subagent_tool":
            curr_task_name = plan_params.get("task_name")
            curr_task = to_do_list.get_task_by_name(curr_task_name)
            
            # 唤醒下一层的 Generator-Agent 执行具体任务

            # 进入第二层循环...
```

### 3.2 Generator-Agent (执行者)

当 `subagent_tool` 被触发后，系统进入内部的 `while True` 循环，唤醒 Generator-Agent。这是真正干活的角色。

为了适应重度代码编写和文件搜索，我为 Generator 赋予了非常宽裕的独立记忆（`keep_latest_n=8, max_chars=80000`），并向它开放了所有的 `base_tool` 和 `search_tool`。

它会在这个子循环中不断尝试：搜索文件 -> 读取代码 -> 修改代码 -> 执行 Bash 脚本测试。在这个过程中，上一节提到的**动态记忆压缩机制**会默默保障它的上下文不会溢出。当 Generator 认为当前子任务已经搞定时，它必须调用一个特殊的工具 `update_task_conclusion` 来提交成果：

```python
                if gen_tool != "update_task_conclusion":
                    # 正常执行基础或搜索工具

                    result = execute_tool(gen_tool, gen_params)
                    generator_memory.add_memory(gen_step, gen_tool, gen_params, result)
                    continue  # 继续第二层循环干活
                else:
                    # Generator 认为完成了，提交结论

                    conclusion = gen_params.get("conclusion", "")
                    to_do_list.update_task_conclusion(curr_task_name, conclusion)
                    # 触发质检，进入第三层循环...
```

### 3.3 Validate-Agent (评估者)

当 Generator 提交成果后，第三层循环启动，Validate-Agent 接管控制权。

它是一个拥有完全独立、清空记忆的全新实例，它的 Prompt 指令明确要求：**验证当前任务的完成是否有效**。它可以自己调用检索或终端工具去核实 Generator 的工作，最后必须调用 `validate_tool` 输出 `有效` 或 `无效` 以及原因。
从而完成**纠错闭环（Feedback Loop）** ：

```python
                            # Validate-Agent 得出验证结论

                            status = val_params.get("status") 
                            reason = val_params.get("reason", "未知错误")

                            if status == "有效":
                                is_valid = True
                                break  # 结束第三层循环，准备回退到第一层
                            else:
                                # 【核心逻辑】验证失败：将错误原因强行写入 Generator 的记忆中

                                generator_memory.add_memory(
                                    gen_step + 1,
                                    "system_feedback",
                                    {},
                                    f"验证失败，请重新调整。原因: {reason}"
                                )
                                is_valid = False
                                break  # 结束第三层循环，回到第二层循环，让 Generator 看到反馈并重试
```

如果验证失败，则会构造了一条名为 `system_feedback` 的内容，注入到 Generator-Agent 的 `WorkingMemory` 中。随后，程序跳出第三层循环，**继续回到第二层循环**。

此时，Generator-Agent 它在上下文里看到了自己之前的操作记录，同时也看到了 Validate-Agent 刚刚打回的“验证失败原因”。基于这些详尽的上下文，Generator 可以立即思考新的解决方案并重试，直到最终通过验证。当验证通过（`is_valid = True`），任务状态才会被真正更新为 `DONE`，控制权重新回到最外层的 Plan-Agent 手中。
