"""Focused authoring guidance, loaded only for rich material requests."""

MATERIALS_GUIDANCE = """
## 精制材料工作流
用户需要可用于授课、汇报或独立学习的材料。按以下流程做到可复查交付。

1. 先 plan_materials：明确受众、先修知识、学习目标、贯穿案例、每页/每章的具体作用和交付标准。
   PPT 的总页数包括封面、结尾。用户要 8 页，就规划且交付恰好 8 页，不用空封面/章节分隔/谢谢页凑数。
   PPT 与 PDF 分别规划。PPT用于现场讲解，PDF让没有讲师的人也能独立学懂。
2. 核对关键事实：优先一手资料，分清官方保证、教学推演和本次实际观察，保存来源。
   有编程案例时围绕同一个完整问题展开：错误现象、逐步推演、修复、修复为何有效、适用条件、练习和详解。
   一次运行正确不能证明并发算法安全，不把人为控制的调度说成自然竞争的固定结果。
   自然竞争示例必须说明可能多次运行仍得到正确值，不能承诺“每次不同”或“几乎不会正确”。需要稳定演示时，另给明确标注的受控交错案例。
3. 使用增强的 create_presentation / create_pdf，传 plan_id。
   长材料先write_material_draft分批保存：一次2-4页幻灯片、1-3章讲义、1-2份源码，每次用返回的draft_id继续追加。
   全部写完后用title + draft_id导出，不再重传全部slides/sections/files。避免一次大JSON导致超时或截断。
   幻灯片混合代码、可编辑table和figure等合适布局，每页一个明确目的，讲解细节写speaker_notes，来源写references。
   需要插画且图片生成已配置时，可generate_image后把真实download_url传cover_image/image。不得编造图片URL。
   PDF使用blocks按教学顺序组织正文、推演表、完整代码、提示、练习与答案。给足推理与前提，不只复制PPT要点。
   练习答案中的源码也用code块；命令和示例输出分开，命令中不混入箭头、说明文字或虚构的实测结果。
   长代码放PDF和源码文件；PPT显示标为节选的关键部分。遇到长度错误应拆分/调整内容，不丢行、不缩成无法阅读。
4. 编程材料用create_code_files交付完整可运行源码和README，文件名与public类名一致。
   若verify_code_examples可用，实际编译并运行，保留日志。工具关闭或缺少运行环境时，明确“未运行验证”。
   提取最终PDF代码再编译是更强核对。没有实际执行结果，禁止声称示例已经跑通。
5. 全部生成后，review_materials(files=[最新PPT链接,最新PDF链接],plan_id=...,visual=true)。
   required_sections仅填必须逐字出现的短文本（例如类名、练习、答案），不要填“封面”等装饰标签或把大纲描述全文当成字面要求。大纲标题允许改写。
   逐页检查实际文件。status=needs_revision时按issues修复并重新审查新文件，不能用旧文件的检查为新文件背书。
   status=partial表示渲染器或视觉模型等检查未完成。可交付现有结果，但必须明确具体未完成范围，不能声称视觉审查通过。
   结构检查不等于内容正确，代码能排版不等于能运行。检查器反馈具体错误时先修正。
6. package_materials打包实际文件，README写阅读顺序、复现命令与已知限制，最后交付各格式和完整包。
   不向用户交付内部计划JSON凑数量。只描述工具证据支持的成果，下载URL从工具结果原样引用。
""".strip()
