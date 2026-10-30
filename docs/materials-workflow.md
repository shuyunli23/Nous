# 精制 PPT 与 PDF 材料

Nous 的材料制作流程现在包括内容规划、文件生成、源码交付、检查和返修。PPT 面向讲解，PDF 面向独立阅读，两种文件共用事实与示例，分别设计内容密度。

## 在界面里使用

在「工作台」创建会话，可以直接发送：

> 面向刚学完 Java 基础的人，制作“线程安全入门”培训材料：一份总计 8 页的 PPT 和一份可独立学习的 PDF 讲义。包括共享计数器错误示例、可编辑的丢失更新交错表、完整修正代码、运行方式、预期现象、三道练习和详解答案。交付完整源码，检查最终文件并说明检查范围。PPT 用于约 40 分钟讲解。

Agent 应当先保存材料计划，再分别制作文件。若用户指定总页数，该数字包含封面和结尾。最后审查两种最终文件，返修时重新生成文件并审查新版本。

长材料可以通过 `write_material_draft` 分批写入：每次 2-4 页幻灯片、1-3 章讲义或 1-2 份源码，最后只传 `draft_id` 导出整份内容，避免在一次模型响应中挤入大段 JSON。中断后，同一会话会恢复计划、文件和草稿标识，Agent 可用 `read_material_draft` 按范围取回正文。直接说「继续」会复用未完成计划；提出修改要求时重新规划，旧审查不自动沿用。

精制任务默认允许 24 轮工作工具调用，连续仅更新清单的上限为 12 轮（实际工作会重置此计数），模型请求等待上限至少 300 秒。普通聊天仍使用原工具预算和供应商超时。可用 `MATERIALS_MAX_TOOL_LOOPS`、`MATERIALS_LLM_TIMEOUT_SECONDS` 配置精制任务的预算；这不会改写已保存的供应商配置。

在「模型设置」的按用途配置中，可以为 **材料审查**（`materials`）选择支持图片输入的聊天模型。未单独指定时回退到当前聊天供应商。该路由用于逐页视觉审查；制作大纲和内容仍由当前会话的模型负责。聊天模型已接通并不代表它能够查看页面图片，也不代表文生图已配置。

图片不是启动前提。没有图片供应商时，仍可以用可编辑表格、代码和清晰的讲解结构制作材料。若需要封面插画，配置图片用途供应商，先生成图片，再把真实导出链接交给材料工具。

## 工具与文件

1. `plan_materials`：保存受众、学习目标、交付物、大纲和验收条件。指定 N 页 PPT 时，大纲需要有 N 个 PPT 条目。
2. `create_presentation`：支持原生可编辑表格、嵌入图片、讲师备注与来源。通过 `plan_id` 或 `expected_slide_count` 严格约束总页数。
3. `create_pdf`：支持有序的段落、代码、表格、图片、提示框和练习答案内容块。长代码可跨页，章节可显式分页。过长单行会要求按语言规则重排，避免截断或盲目拆坏字符串。
4. `create_code_files`：按原始文件名交付 UTF-8 源码 ZIP，并返回专用工作区。创建源码不代表运行过源码。
5. `verify_code_examples`：调用既有命令工具执行明确的编译、运行命令。它受命令执行开关、工作区与权限上限约束，返回实际命令、输出和源码哈希。
6. `review_materials`：读取最终文件的实际内容，渲染逐页预览，检查结构，并可调用材料审查模型检查页面。文件哈希将审查结果绑定到具体版本。
7. `package_materials`：只打包明确选中的文件，并附阅读顺序及运行说明。打包成功不代表内容审查成功。

材料图片必须来自受管 `data/uploads` 或 `data/exports`；生成器不会任意读取服务器文件或下载外部图片。正常导出和下载继续使用现有文件 API。

## 渲染环境

PDF 的逐页渲染使用 PyMuPDF。PPTX 先通过 LibreOffice 转成 PDF，再生成预览图。安装 LibreOffice 并确保 `soffice` 或 `libreoffice` 在 PATH 中，或设置可执行文件绝对路径：

```powershell
$env:NOUS_LIBREOFFICE = 'C:\Program Files\LibreOffice\program\soffice.exe'
```

```bash
export NOUS_LIBREOFFICE=/usr/bin/libreoffice
```

`NOUS_LIBREOFFICE` 是后端进程的环境变量，设置后需要让启动后端的进程继承它。转换使用独立临时 LibreOffice 配置，避免与桌面会话争用用户配置。Docker 镜像包含相应渲染和字体依赖；本地运行时也要安装可嵌入的中文字体。Linux 可使用 WenQuanYi TrueType 字体和 DejaVu 等宽字体。缺少适用中文字体时，PDF 会明确报错，不静默输出缺字。

## 如何理解审查结果

- `review_scope=visual_and_structural`：本次请求结构与视觉审查。只有所有页面实际可渲染、模型成功审查后，才会有 `visual_review_complete=true`。
- `status=partial`：有必要检查无法完成，例如缺少 LibreOffice、模型不支持图片或调用失败。不能声称已通过完整视觉审查。
- `status=needs_revision`：发现明确问题。根据 `issues` 修改，再对新文件重新审查。
- `visual=false`：仅结构检查。即使此范围内 `status=passed`，也不代表视觉或内容语义已经全面正确。
- 文档审查报告里的 `code_execution=not_run` 是独立范围说明。代码是否实际运行，要看 `verify_code_examples` 的单独日志。

结构检查能核对页数、空内容、文本缺字等；视觉模型可以指出溢出、重叠和可读性问题，但两者都不能替代领域知识审校或正确性证明。输出质量仍受会话模型、审查模型、工具环境和任务预算影响，不承诺任意模型都得到相同结果。

## 复现实例与验收

从 `backend` 目录运行，不需要模型密钥或图片供应商：

```text
python scripts/smoke_materials.py
```

此脚本走真实材料工具，生成《Java 线程安全入门》8 页 PPT、丰富讲义、五个完整 Java 程序、材料计划、结构检查报告和整套 ZIP。PPT 包含原生交错表与讲师备注，PDF 包含错误与修正程序、逐步推演、三道练习及详解。所有原件保存在受管 `data/exports`，打印出的下载链接可以由正在运行的 Nous 后端提供。

需要将交付物额外复制到其他目录时：

```text
python scripts/smoke_materials.py --output-dir C:/Temp/nous-materials
```

`--output-dir` 是额外交付目录。服务器管理的原件仍保留在 `data/exports`，API 下载链接仍指向这些原件。不要只移动某一份原件后仍使用旧下载链接。

如已安装 JDK 17 或更新版本，可显式执行固定示例代码：

```text
python scripts/smoke_materials.py --verify-code
```

脚本优先查 PATH 中的 `javac`，其次查 `JAVA_HOME`，并兼容 Windows Android Studio 的内置 JDK。`--verify-code` 只在该脚本进程中为临时工作区启用运行，结束后清理工作区，不保存或改写 `shell_config.json`，不为运行中的 Nous 服务开启命令执行。该演示固定运行自己的示例，生产 Agent 要运行生成代码时，仍应由用户在设置中开启命令执行。

验收重点：

- PPT 实际总页数必须为 8，交错表仍是可编辑表格，备注有讲解和来源。
- 所有源码文件名与 `public class` 一致，完整程序可独立编译。
- SafeCounter、AtomicCounter 正常完成时输出 `actual=200000`。
- ForcedRace 输出 `expected=2 actual=1`；这是受控教学调度。
- TicketOffice 输出 `sold=1 remaining=0`。
- UnsafeCounter 的具体输出不固定，也可能恰好得到 200000。观察到正确结果不能证明线程安全。
- 讲义不把教学推演当成实测，不把 `join`、可见性和原子性混为一谈。
- 脚本默认 `visual=false`，会诚实报告仅结构检查。完整视觉审查需要在工作台中配置相应模型并调用 `review_materials(visual=true)`。

此脚本验收工具链和固定教学案例，不验收模型自由生成内容的能力。还应使用多种受众、主题、长代码、表格和资料冲突任务进行实际会话测试。
