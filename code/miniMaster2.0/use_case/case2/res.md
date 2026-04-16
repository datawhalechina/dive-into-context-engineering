# miniMaster2.0 项目综合检查报告 — 面向初学者中文说明

---

## 一、项目目录结构概览

miniMaster2.0 项目根目录包含以下关键文件和文件夹：

| 名称 | 类型 | 作用简述 |
|------|------|----------|
| `main_agent.py` | 文件 | 项目主入口，启动三层 Agent 循环 |
| `requirements.txt` | 文件 | Python 依赖声明 |
| `log.txt` | 文件 | 运行日志，记录 Agent 执行过程 |
| `项目报告.md` | 文件 | 项目原有说明文档 |
| `prompting/` | 目录 | 提示词构造模块，包含 `builders.py`、`policies.py` 等 |
| `tools/` | 目录 | 工具定义与执行模块 |
| `utils/` | 目录 | 通用辅助工具 |
| `app/` | 目录 | 应用启动与初始化（含 `bootstrap.py`） |
| `runtime/` | 目录 | 运行时相关配置 |
| `__pycache__/` | 目录 | Python 编译缓存（自动生成） |

---

## 二、Workspace（工作目录）是什么？

### 定义

**Workspace** 就是 Agent 的"工作空间"——即 Agent 执行任务时所处的根目录路径。在本项目中，workspace 被定义为项目根目录的绝对路径，在 `app/bootstrap.py` 中通过以下代码计算：

```python
workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

这行代码的意思是：取当前文件（`bootstrap.py`）的绝对路径，再往上跳两级目录，得到的就是项目根目录。例如本项目 workspace 为 `C:\Users\25853\Desktop\self-harness\code\miniMaster2.0`。

### 为什么要显式告诉 Agent workspace？

在 `prompting/builders.py` 的 `build_workspace_block()` 函数中，workspace 被转换成一段说明文本并注入到 Prompt 中，核心内容如下：

```
当前工作目录是：{workspace_path}
当用户提到"当前目录""这里""本项目目录"时，默认指这个工作目录。
未特别说明时，工具中的相对路径都会相对于这个工作目录解析。
```

**为什么要这么做？** 因为：

1. **路径解析依赖 workspace**：Agent 调用工具（如读文件、写文件）时，如果不明确知道工作目录，相对路径就会解析到错误的位置。例如用户说"读取 config.json"，Agent 需要知道这是相对于哪个目录的。
2. **语言理解依赖 workspace**：用户经常用"当前目录""这里""本项目"这类模糊说法指代路径。如果 Prompt 里没有写明 workspace，大模型可能会把"当前目录"误解成系统临时目录、用户 home 目录等别处。
3. **稳定性提升**：把 workspace 明确写进 Prompt 后，Agent 在处理文件定位任务时会更加稳定，不会因为路径歧义而出错。

---

## 三、Agent 为何需要知道当前目录？

Agent 是一个在特定环境中执行任务的程序，而不是一个无所不知的"万能大脑"。它需要知道当前目录，原因有三：

1. **任务上下文锚定**：几乎所有文件操作都依赖于"我在哪里"。Agent 不知道当前目录，就像一个人不知道自己站在哪个房间，却要去找某个柜子里的文件——必然会迷路。

2. **自然语言歧义消除**：用户说"帮我检查这里的配置文件"，"这里"到底指哪里？如果 Prompt 里明确写了 `当前工作目录是：C:\Users\25853\Desktop\self-harness\code\miniMaster2.0`，Agent 就不会误解。

3. **工具调用的准确性**：本项目的工具系统在 `tools/core.py` 和 `tools/` 各子模块中实现，它们在解析相对路径时默认使用 workspace 作为基准。Agent 知道当前目录后，才能正确构造工具调用参数。

`prompting/builders.py` 中还有一个 `build_execution_context_block()` 函数，它把工作目录信息和运行环境信息合并成一个统一的"执行上下文块"注入 Prompt，让 Agent 同时了解"我在哪里"和"我在什么系统上运行"。

---

## 四、Windows 下不能随意用 `ls -a` 的原因

### 核心原因：`ls -a` 是 Linux/Unix 命令，不是 PowerShell 命令

在 Linux/Mac 终端（bash/zsh）中，`ls -a` 表示"列出所有文件，包括隐藏文件"，这是一个标准的 Unix 命令。

但在 Windows 系统下，本项目运行环境使用的是 **PowerShell**，而非 bash。PowerShell 中：

- **`ls`** 实际上是 `Get-ChildItem` 的别名，但它**不支持 `-a` 参数**。`-a` 在 PowerShell 中没有定义，执行 `ls -a` 会报错或产生意外行为。
- **正确替代方案**：要列出包含隐藏项的目录，应使用 `Get-ChildItem -Force`。

### 项目中如何处理这个问题？

在 `prompting/builders.py` 的 `build_runtime_environment_block()` 函数中，系统会根据 `system_name`（如 `"Windows"`）和 `command_shell`（如 `"PowerShell"`）自动生成运行环境说明文本，明确告知 Agent：

```
当前运行环境是 Windows。
bash 工具当前通过 PowerShell 执行命令。
如果任务是列目录、找文件、搜文本，优先使用 glob / grep / read 这类专用工具，不要先默认使用 bash。
如果确实要用 bash 查看目录，可使用 ls 或 Get-ChildItem；如果要包含隐藏项，请使用 Get-ChildItem -Force，不要使用 ls -a。
```

这样做是为了防止 Agent 在 Windows 环境下误用 Unix 命令，导致执行失败。这也是 `build_execution_context_block()` 把运行环境和工作目录一起注入 Prompt 的原因——让 Agent 知道"我在 Windows + PowerShell 上"，从而选择正确的命令。

---

## 五、三层 Agent 的各自职责

miniMaster2.0 采用**三层 Agent 协作架构**，每一层有明确的职责分工，定义在 `prompting/builders.py`（提示词构造）和 `prompting/policies.py`（动作策略）中。

### 1. Plan-Agent（计划 Agent）

**职责**：将用户的整体需求（user_query）分解为一系列有序的子任务（task list）。

- 它不直接执行任何工具，只做"规划"。
- 它分析用户意图，把复杂任务拆成可逐步执行的子任务，每个子任务包含 `task_name`、`task_status` 等字段。
- 对应的提示词构造函数：`build_plan_prompt()`，它接收 `user_query` 和已有任务列表，生成 Plan-Agent 的 Prompt。
- Plan-Agent 可用的动作（在 `policies.py` 中定义）：主要是任务分解和状态管理相关动作。

**通俗比喻**：Plan-Agent 就像项目经理，接到客户需求后制定任务清单，分配给下面的人去做，自己不亲自动手。

### 2. Generator-Agent（生成/执行 Agent）

**职责**：接收 Plan-Agent 分配的单个子任务，选择合适的工具并执行，产生具体输出。

- 它是"干活的人"，会调用项目中的各种工具（如 `read`、`write`、`bash`、`glob`、`grep`、`edit` 等）来完成具体操作。
- 对应的提示词构造函数：`build_generator_prompt()`，它接收当前任务详情、可用工具列表、工作目录和运行环境信息，生成 Generator-Agent 的 Prompt。
- Generator-Agent 的动作策略在 `policies.py` 中定义，包括工具选择和执行参数的规则。

**通俗比喻**：Generator-Agent 就像执行工程师，拿到任务单后选择合适的工具（锤子、螺丝刀、测量仪），一步步完成具体操作。

### 3. Validate-Agent（验证 Agent）

**职责**：检查 Generator-Agent 的执行结果是否正确、是否满足任务要求。

- 它使用 `validate_tool` 来验证前一步的输出。例如：验证文件是否已创建、内容是否非空、搜索结果是否包含预期关键词等。
- 对应的提示词构造函数：`build_validate_prompt()`，它接收当前任务、Generator 的执行结果、验证标准等，生成 Validate-Agent 的 Prompt。
- Validate-Agent 的动作策略在 `policies.py` 中定义，核心动作就是 `validate_tool`。

**通俗比喻**：Validate-Agent 就像质检员，在工程师做完活之后检查成品是否符合要求，不合格就打回去重做。

### 三层协作流程

```
用户需求 (user_query)
    → Plan-Agent 分解为子任务列表
        → Generator-Agent 执行某个子任务
            → Validate-Agent 验证执行结果
                → 结果合格 → 进入下一个子任务
                → 结果不合格 → 回退，调整并重新执行
```

这种循环机制保证了每个子任务都有"做→检查→确认/修正"的完整闭环，避免"做了但没验证"导致的隐性错误。

---

## 六、validate_tool 相关实现

`validate_tool` 是 Validate-Agent 专用的验证工具，在项目日志 `log.txt` 中多次出现：

```
🛠️  Validate-Agent 选择工具: validate_tool
✅ 工具执行结果: {'success': True, 'content': '...'}
```

`validate_tool` 的核心功能是：
- 检查 Generator-Agent 执行后的产出是否满足任务预期条件
- 返回 `success: True/False` 表示验证是否通过
- 返回具体 `content` 描述验证细节

它在 `prompting/policies.py` 中被定义为 Validate-Agent 的可用动作之一，确保只有 Validate-Agent 可以调用验证逻辑，而 Plan-Agent 和 Generator-Agent 不能自行验证自己的输出。

---

## 七、总结

| 关键概念 | 一句话说明 |
|----------|-----------|
| Workspace | Agent 执行任务时的根目录路径，决定了相对路径如何解析 |
| 当前目录的重要性 | 不告诉 Agent 当前目录，它就无法正确理解"这里""本项目"等模糊表述 |
| Windows 下 ls -a 不可用 | `ls -a` 是 Unix 命令，Windows PowerShell 应使用 `Get-ChildItem -Force` |
| Plan-Agent | 项目经理——只做规划，把需求拆成子任务 |
| Generator-Agent | 执行工程师——选择工具，动手干活 |
| Validate-Agent | 质检员——检查执行结果是否合格 |

本报告基于对 miniMaster2.0 项目中 `prompting/builders.py`、`prompting/policies.py`、`app/bootstrap.py`、`tools/`、`utils/` 等关键代码文件的阅读和搜索结果整理而成。