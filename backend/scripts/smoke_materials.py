"""Exercise Nous' real material tools without an LLM or image API.

Run from backend: python scripts/smoke_materials.py [--verify-code]
Generated originals always remain in managed data/exports. --output-dir copies
the finished deliverables elsewhere without changing their server URLs.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

from app.core.config import settings
from app.agent.tools.builtins import create_pdf, create_presentation
from app.agent.tools.material_workflow import (
    create_code_files, package_materials, plan_materials, verify_code_examples,
)
from app.agent.tools.material_schemas import _review as review_materials
from app.agent.tools import shell_config

TITLE = "Java 线程安全入门"
REFERENCES = [
    {"title": "JLS 17.1 与 17.4.5：监视器、同步及 happens-before", "url": "https://docs.oracle.com/javase/specs/jls/se17/html/jls-17.html"},
    {"title": "Thread API：start、run、join", "url": "https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/lang/Thread.html"},
    {"title": "AtomicInteger API", "url": "https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/util/concurrent/atomic/AtomicInteger.html"},
]
OBJECTIVES = ["画出一次丢失更新", "运行错误与修正程序", "解释 join、volatile 和锁的作用", "识别原子方法组合后的业务竞态"]


def counter_source(name: str, *, synchronized: bool = False, atomic: bool = False) -> str:
    field = "private final AtomicInteger count = new AtomicInteger();" if atomic else "private int count;"
    increment = "count.incrementAndGet();" if atomic else "count++;"
    read = "count.get()" if atomic else "count"
    modifier = "synchronized " if synchronized else ""
    imports = "import java.util.concurrent.atomic.AtomicInteger;\n\n" if atomic else ""
    assertion = ('        if (actual != 200000) throw new AssertionError("Lost update");\n'
                 if synchronized or atomic else '')
    return imports + f'''public class {name} {{
    {field}
    public {modifier}void increment() {{ {increment} }}
    public int get() {{ return {read}; }}

    public static void main(String[] args) throws InterruptedException {{
        {name} counter = new {name}();
        Runnable task = () -> {{
            for (int i = 0; i < 100000; i++) counter.increment();
        }};
        Thread a = new Thread(task);
        Thread b = new Thread(task);
        a.start();
        b.start();
        a.join();
        b.join();
        int actual = counter.get();
        System.out.printf("expected=200000 actual=%d%n", actual);
{assertion}    }}
}}
'''


FORCED = '''import java.util.concurrent.CountDownLatch;

public class ForcedRace {
    private static int count;
    public static void main(String[] args) throws InterruptedException {
        CountDownLatch read = new CountDownLatch(2);
        CountDownLatch write = new CountDownLatch(1);
        Runnable task = () -> {
            int old = count;
            read.countDown();
            try {
                write.await();
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
                return;
            }
            count = old + 1;
        };
        Thread a = new Thread(task);
        Thread b = new Thread(task);
        a.start(); b.start();
        read.await();
        write.countDown();
        a.join(); b.join();
        System.out.printf("expected=2 actual=%d%n", count);
        if (count != 1) throw new AssertionError("Unexpected result");
    }
}
'''
TICKETS = '''public class TicketOffice {
    private int remaining = 1;
    public synchronized boolean buyOne() {
        if (remaining > 0) {
            remaining--;
            return true;
        }
        return false;
    }
    public static void main(String[] args) throws InterruptedException {
        TicketOffice office = new TicketOffice();
        boolean[] bought = new boolean[2];
        Thread a = new Thread(() -> bought[0] = office.buyOne());
        Thread b = new Thread(() -> bought[1] = office.buyOne());
        a.start(); b.start();
        a.join(); b.join();
        int sold = (bought[0] ? 1 : 0) + (bought[1] ? 1 : 0);
        System.out.printf("sold=%d remaining=%d%n", sold, office.remaining);
        if (sold != 1 || office.remaining != 0) {
            throw new AssertionError("Inventory invariant violated");
        }
    }
}
'''
RUNNING = """javac -encoding UTF-8 UnsafeCounter.java
javac -encoding UTF-8 SafeCounter.java
javac -encoding UTF-8 AtomicCounter.java
javac -encoding UTF-8 ForcedRace.java
javac -encoding UTF-8 TicketOffice.java
java UnsafeCounter
java SafeCounter
java AtomicCounter
java ForcedRace
java TicketOffice"""
TRACE_COLUMNS = ["步骤", "线程 A", "线程 B", "count"]
TRACE_ROWS = [["1", "读取 0，记住 a=0", "等待", "0"],
              ["2", "等待", "读取 0，记住 b=0", "0"],
              ["3", "写回 a+1，即 1", "等待", "1"],
              ["4", "完成", "写回 b+1，即 1", "1"]]
QUESTIONS = [
    ("画出丢失更新", "从 count=0 开始，两个线程各自执行一次 count++。写出最终为 1 的交错。",
     "A 和 B 都先读到旧值 0。A 写回 1 后，B 仍用自己记住的 0 算出 1，再写回同一字段。两次调用仅保留一次加一效果。修复需要保护完整读改写，或采用一个原子自增操作。"),
    ("普通 getter 与 join", "increment 同步，get 普通读取。两个工作线程都 join 正常返回且无后续写入，能否读到最终 200000？",
     "可以。第一层是同一把锁保护自增，不丢更新。第二层是两个线程终止与主线程 join 的正常返回建立 happens-before，最终写入对随后的普通读取可见。去掉 join 可能尚未算完，也失去这个读取可见性依据。只等待一个线程或只使用可能超时返回的 join，条件都不充分。"),
    ("修复库存超卖", "AtomicInteger 库存先 get()>0 再 decrementAndGet()，为什么可能卖出两张票？如何修复？",
     "库存为 1 时，A、B 都可能先读到 1，通过判断后各减一次，库存变成 -1。每个方法原子，并不让组合业务原子。TicketOffice 用同一个实例的 synchronized buyOne 包住检查、扣减和成功返回。两个买家结束后应当恰好成功一次，remaining=0；谁成功不固定。"),
]


def presentation() -> list[dict]:
    notes = "完整可运行程序在源码 ZIP 中。两个线程必须共享一个实例，先都 start，再分别 join。"
    slides = [
        {"layout": "title", "heading": TITLE, "subtitle": "共享计数器实验课\n面向刚学完 Java 基础的学习者", "speaker_notes": "约40分钟。先让学员预测两个线程各加100000次的结果，不急着公布答案。"},
        {"layout": "code", "heading": "错误示例：共享字段的自增", "language": "java",
         "code": "class UnsafeCounter {\n    private int count;\n    void increment() { count++; }\n    int get() { return count; }\n}",
         "explain": ["两个线程共享同一个实例", "每个线程自增 100000 次", "期望总数为 200000", "一次正确结果不能证明安全"], "speaker_notes": notes},
        {"layout": "table", "heading": "丢失更新的发生过程", "columns": TRACE_COLUMNS, "rows": TRACE_ROWS,
         "caption": "教学推演：两次自增最终只增加 1，不是实际调度日志。", "speaker_notes": "逐行推演，停在第2步让学员预测。各线程记住的局部旧值不会自动变化。"},
        {"layout": "code", "heading": "修正代码：同一把锁保护整个操作", "language": "java",
         "code": "class SafeCounter {\n    private int count;\n    synchronized void increment() {\n        count++;\n    }\n    int get() { return count; }\n}",
         "explain": ["实例同步方法锁住 this", "所有写线程使用同一个对象", "读、计算和写回都在锁内", "get 仅在两个 join 后调用"], "speaker_notes": notes + "锁不禁止CPU切换，它阻止其他线程同时取得同一监视器进入受保护区域。"},
        {"layout": "table", "heading": "等待、可见性和原子性", "columns": ["机制", "保证", "能修复自增吗"],
         "rows": [["join", "等线程终止，发布完成结果", "不能协调两个写线程"], ["volatile", "字段读写的可见性与顺序", "不能合并读改写"], ["synchronized", "同锁互斥及可见性", "完整操作在同锁内即可"], ["AtomicInteger", "单次原子更新方法", "用 incrementAndGet"]],
         "caption": "join 后能看见最终值，也可能看见一个少算了的值。", "speaker_notes": "两个工作线程均已终止，join正常返回，且之后没有新写入。可见性不会追回已经丢失的更新。"},
        {"layout": "code", "heading": "原子方法组合后的业务竞态", "language": "java",
         "code": "if (stock.get() > 0) {\n    stock.decrementAndGet();\n    return true;\n}",
         "explain": ["初始只有一张票", "两位买家都可能先看到 1", "两个扣减可能让库存变负", "同一把锁包住判断与扣减"], "speaker_notes": "AtomicCounter是正确的单变量自增。库存规则需要整体保护，完整修正程序为TicketOffice.java。"},
        {"layout": "code", "heading": "运行方式与预期现象", "language": "terminal", "code": RUNNING,
         "explain": ["JDK 17 或更新版本", "Unsafe 也可能碰巧正确", "Safe、Atomic 应为 200000", "ForcedRace 稳定演示 1"], "speaker_notes": "自然竞争没有固定错误数字。ForcedRace是人为控制读取与写入时机的教学程序；未启用verify-code时，材料不会声称已经实测。"},
        {"layout": "bullets", "heading": "三道练习", "bullets": ["写出从 0 得到 1 的自增交错", "解释同步自增、普通 get 与 join 的条件", "修复库存先判断再扣减的竞态"],
         "speaker_notes": "\n\n".join(f"练习：{q}\n参考答案：{a}" for _, q, a in QUESTIONS)},
    ]
    for slide in slides:
        slide["references"] = REFERENCES
    return slides


def handbook(sources: dict[str, str], observation: str) -> list[dict]:
    def para(text): return {"type": "paragraph", "text": text}
    def code(text, caption="完整源码", language="java"): return {"type": "code", "code": text, "language": language, "caption": caption}
    sections = [
        {"heading": "1. 线程如何共享状态", "body": "本课只要求了解变量、循环、类和方法。() -> { ... } 表示交给线程执行的一段任务。两个工作线程拿到同一个计数器实例，因此修改同一个 count 字段；各自的循环变量 i 是局部值。",
         "blocks": [{"type": "table", "columns": ["调用", "作用"], "rows": [["new Thread(task)", "创建线程对象，尚未运行任务"], ["start()", "启动新线程，执行任务"], ["run()", "普通方法调用，在当前线程执行"], ["join()", "当前线程等待目标线程终止"]]},
                    {"type": "callout", "title": "先找共享状态", "text": "共享的是同一个实例的字段。每个线程各 new 一个计数器时，已经换了问题。先启动两个线程，再等待两个线程，避免无意中把整个工作串行化。"}]},
        {"heading": "2. 错误示例：可运行的共享计数器", "page_break_before": True,
         "body": "保存为 UnsafeCounter.java。完整程序包括入口、两个工作线程、循环、完成等待与结果输出。预期完成 200000 次自增，但 count++ 是复合更新。",
         "blocks": [code(sources["UnsafeCounter.java"]), para("多运行几次可能看见少计，也可能碰巧每次正确。增加循环次数会改变暴露错误的机会，不能把它当成修复。不要在每次自增时打印：打印会改变调度并影响实验。")]},
        {"heading": "3. 一次丢失更新的全过程", "page_break_before": True,
         "body": "把 count++ 按读旧值、计算加一、写回理解。下表是帮助理解的简化交错，不代表固定 CPU 指令数量或 JVM 的所有执行情况。",
         "blocks": [{"type": "table", "columns": TRACE_COLUMNS, "rows": TRACE_ROWS},
                    para("A 和 B 都基于 0 得到 1。B 后写回时覆盖 A 的一次更新效果，所以两次调用最后只增加 1。局部旧值不会因为共享字段后来改变而自动更新。"),
                    {"type": "table", "columns": ["概念", "关注的问题"], "rows": [["原子性", "能否把一次复合更新作为整体协调"], ["可见性", "另一个线程何时有规则保证看见写入"], ["有序性", "哪些先后关系由内存模型保证"]]}]},
        {"heading": "4. 修正代码：synchronized", "page_break_before": True,
         "body": "保存为 SafeCounter.java，运行 java SafeCounter。实例同步方法统一使用当前对象的监视器，两个线程共享同一个对象，所以同一时刻只能有一个线程进入完整自增。",
         "blocks": [code(sources["SafeCounter.java"]), para("所有竞争访问应遵守同一协议。每次 synchronized(new Object()) 会创建不同锁；共享静态字段却对不同实例各自加锁，同样无法建立所需互斥。持有锁仍可能被操作系统暂停，锁的作用不是禁止调度。")]},
        {"heading": "5. join 的保证与使用前提", "page_break_before": True,
         "body": "本例的 getter 没有同步，是有意限定的最终读取：两个写线程使用同一把锁自增；两个不带超时的 join 都正常返回；此后没有任何新写入。线程终止与 join 正常返回建立 happens-before，最终写入对主线程之后的普通读取可见。",
         "blocks": [{"type": "callout", "title": "两个层面分别分析", "text": "同锁互斥保证计数过程不丢失。join 保证工作完成，并为最终读取提供可见性。UnsafeCounter 也执行 join，但过去已经丢失的更新不会因此恢复。"},
                    {"type": "table", "columns": ["改动", "为何需要重新分析"], "rows": [["去掉 join", "可能还没完成，并且缺少此处的可见性依据"], ["只等一个线程", "另一个可能继续写入"], ["使用 join(timeout)", "超时返回不等于线程已结束"], ["join 后出现新写入", "最终只读阶段的前提不成立"]]}]},
        {"heading": "6. 修复二：AtomicInteger", "page_break_before": True,
         "body": "保存为 AtomicCounter.java。incrementAndGet 对单次自增提供原子更新。不要重写成 set(get()+1)，那会再次拆成多个操作。把 int 改成 volatile int 也不能自动把 count++ 合成原子更新。",
         "blocks": [code(sources["AtomicCounter.java"]), para("本课不比较性能。原子类适合这种单变量原子更新，但并不自动维护多个对象、多个调用或整个业务规则的一致性。")]},
        {"heading": "7. 运行方式、预期现象和本次检查", "page_break_before": True,
         "body": "把源码 ZIP 解压到同一目录，准备 JDK 17 或更新版本。在终端进入源码目录后逐行执行：",
         "blocks": [code(RUNNING, "在源码所在目录执行", "terminal"),
                    {"type": "table", "columns": ["程序", "应如何判断"], "rows": [["UnsafeCounter", "可能少于200000，也可能恰好正确"], ["SafeCounter / AtomicCounter", "正常完成时应为200000"], ["ForcedRace", "教学控制调度，期望2但实际1"], ["TicketOffice", "售出1张，remaining=0，买家身份不固定"]]},
                    {"type": "callout", "title": "本次命令执行状态", "text": observation}]},
        {"heading": "8. 选读：稳定演示丢失更新", "page_break_before": True,
         "body": "ForcedRace.java 使用门闩确保两个线程都先读 0，再允许写回 1。先运行观察即可，本课不要求掌握 CountDownLatch。它是教学控制调度，不是自然压力测试，也不是 JVM 必须采用的执行顺序。",
         "blocks": [code(sources["ForcedRace.java"])]},
        {"heading": "9. 原子方法也有业务边界", "page_break_before": True,
         "body": "只有一张票，两个买家分别 get()>0 再 decrementAndGet，都可能先看到 1 并通过条件，随后库存变成 -1。每个方法原子，不代表组合业务原子。业务约束是库存不负、成功次数不超过初始票数。",
         "blocks": [code("if (stock.get() > 0) {\n    stock.decrementAndGet();\n    return true;\n}", "错误的复合业务操作"),
                    para("入门修复方案是用同一把锁包住完整判断、扣减与成功结果。进阶可学习 CAS 循环，但比较失败后仍需重新读取并检查条件。下文练习 3 提供完整修正代码。")]},
        {"heading": "10. 三道练习", "page_break_before": True,
         "blocks": [{"type": "exercise", "title": f"练习 {i}：{title}", "question": q} for i, (title, q, _) in enumerate(QUESTIONS, 1)]},
        {"heading": "11. 参考答案与推理", "page_break_before": True,
         "blocks": [{"type": "exercise", "title": f"答案 {i}：{title}", "answer": answer} for i, (title, _, answer) in enumerate(QUESTIONS, 1)]},
        {"heading": "12. 库存练习的完整实现", "page_break_before": True,
         "blocks": [code(sources["TicketOffice.java"], "TicketOffice.java"), para("所有买家共用 office，buyOne 锁住同一实例。主线程在两个 join 后才读取 bought 与 remaining。营业过程中若允许随时查询库存，查询也必须采用合适的同步机制。")]},
        {"heading": "13. 排错与复习", "page_break_before": True,
         "blocks": [{"type": "table", "columns": ["现象", "检查方向"], "rows": [["找不到 javac", "检查安装的是完整JDK并配置PATH"], ["找不到主类", "在源码目录编译，运行命令用类名"], ["错误版碰巧正确", "这不构成证明，运行ForcedRace观察机制"], ["同步后仍然少计", "同一实例、同一锁、完整更新、等待全部完成"], ["sleep之后似乎好了", "休眠不提供同步保证"]]},
                    para("复习时先说明共享状态，再说明完整操作与约束，最后指出保证来自哪一种规则。课堂中的观察记录不构成错误概率或性能结论，也不替代技术审查。此例只讨论同一 JVM 内存对象，不代表跨服务库存方案。") ]},
    ]
    return sections


def require(result: dict, stage: str) -> dict:
    if not result.get("ok"):
        raise RuntimeError(f"{stage}: {result.get('error') or result}")
    return result


def java_commands(names: list[str]) -> list[str]:
    compiler = shutil.which("javac")
    if not compiler:
        candidates = []
        if os.environ.get("JAVA_HOME"):
            candidates.append(Path(os.environ["JAVA_HOME"]) / "bin" / ("javac.exe" if os.name == "nt" else "javac"))
        if os.name == "nt":
            candidates.append(Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Android/Android Studio/jbr/bin/javac.exe")
        compiler = next((str(p) for p in candidates if p.is_file()), None)
    if not compiler:
        raise RuntimeError("--verify-code needs JDK 17+ with javac on PATH or JAVA_HOME.")
    java = Path(compiler).with_name("java.exe" if os.name == "nt" else "java")
    def invoke(executable):
        return "& '" + str(executable).replace("'", "''") + "'" if os.name == "nt" else shlex.quote(str(executable))
    return [invoke(compiler) + " -encoding UTF-8 --release 8 -Xlint:-options " + " ".join(names)] + [invoke(java) + " " + Path(name).stem for name in names]


async def run(args: argparse.Namespace) -> int:
    exports = settings.resolve_path("./data/exports")
    exports.mkdir(parents=True, exist_ok=True)
    sources = {"UnsafeCounter.java": counter_source("UnsafeCounter"),
               "SafeCounter.java": counter_source("SafeCounter", synchronized=True),
               "AtomicCounter.java": counter_source("AtomicCounter", atomic=True),
               "ForcedRace.java": FORCED, "TicketOffice.java": TICKETS}
    slides = presentation()
    plan = require(await plan_materials(title=TITLE, audience="刚学完 Java 基础的学习者", objectives=OBJECTIVES,
        deliverables=[{"kind": "pptx", "purpose": "40分钟课堂讲解", "total_slides": 8}, {"kind": "pdf", "purpose": "独立复现与课后练习"}],
        outline=[{"kind": "pptx", "heading": item["heading"], "purpose": item["speaker_notes"]} for item in slides]
                + [{"kind": "pdf", "heading": section["heading"], "purpose": section.get("body") or "提供本章完整代码、可复验步骤或习题推理。"}
                   for section in handbook(sources, "尚未执行代码验证。")],
        acceptance_criteria=["PPT总页数为8", "交错表可编辑", "完整源码可独立编译", "模拟与实测清楚区分"], references=REFERENCES), "plan")
    verification: dict = {"ok": True, "verification_status": "not_run", "message": "未指定 --verify-code。源码未在本次演示中编译或运行，材料中的数字仅是预期现象。"}
    with tempfile.TemporaryDirectory(prefix="nous-material-smoke-") as temporary:
        # This process-only overlay never writes shell_config.json and cannot
        # make the running Nous server start accepting arbitrary shell calls.
        with patch.object(settings, "shell_workspace_dir", str(Path(temporary))), patch.object(settings, "shell_network_enabled", False):
            resolved = replace(shell_config.resolve_shell(), enabled=args.verify_code,
                               default_mode="workspace-write", max_mode="workspace-write")
            with patch.object(shell_config, "resolve_shell", return_value=resolved):
                code = require(await create_code_files(title=TITLE, files=[{"filename": name, "content": value} for name, value in sources.items()]
                    + [{"filename": "README.md", "content": "# 运行示例\n\n准备JDK17+，在此目录逐行执行：\n\n```text\n" + RUNNING + "\n```\n\nUnsafe结果不固定；ForcedRace人为控制调度。"}]), "sources")
                if args.verify_code:
                    commands = java_commands(list(sources))
                    verification = await verify_code_examples(workspace=code["workspace"], commands=commands)
        observation = verification.get("message", "")
        if verification.get("verification_status") == "passed":
            observation = "本次已实际编译并运行以下源码。以下是终端原始输出，属于一次观察，不是固定错误数字、错误概率或性能排名。\n\n" + "\n".join(
                f"{row['command'].split()[-1]}: {row.get('stdout', '').strip()}" for row in verification.get("commands", []) if row.get("stdout", "").strip())
        elif verification.get("verification_status") == "failed":
            observation = "本次编译或运行未通过。请查看独立验证日志；不得把材料当作已运行通过。"
        deck = require(await create_presentation(title=TITLE, slides=slides, plan_id=plan["plan_id"], theme="ink"), "PPT")
        pdf = require(await create_pdf(title=TITLE + "：实验与自学讲义", sections=handbook(sources, observation), plan_id=plan["plan_id"]), "PDF")
        review = require(await review_materials(files=[deck["download_url"], pdf["download_url"]], plan_id=plan["plan_id"], visual=False,
            required_sections=["错误示例", "修正代码", "丢失更新", "运行方式", "预期现象", "练习", "参考答案"]), "review")
        selected = [deck["path"], pdf["path"], code["path"], review["path"], str(exports / f"material_plan_{plan['plan_id']}.json")]
        if verification.get("path"):
            selected.append(verification["path"])
        kit = require(await package_materials(title=TITLE, files=selected,
            readme="# 阅读顺序\n\n先看8页PPT，再读PDF，并解压sources.zip运行源码。\n\n代码状态：" + verification["verification_status"]
                   + "\n审查范围：structural_only。未进行模型视觉审查，不能声称已通过完整视觉检查。\n\n运行方式：\n```text\n" + RUNNING + "\n```"), "package")
    output = Path(args.output_dir).expanduser().resolve() if args.output_dir else exports
    output.mkdir(parents=True, exist_ok=True)
    final_paths = selected + [kit["path"]]
    if output != exports.resolve():
        for name in final_paths:
            source = Path(name)
            if source.resolve() != (output / source.name).resolve():
                shutil.copy2(source, output / source.name)
    summary = {"plan_id": plan["plan_id"], "slide_count": deck["slide_count"], "pdf_page_count": pdf["page_count"],
               "code_verification": verification["verification_status"], "review_status": review["status"],
               "review_scope": review["review_scope"], "visual_review_complete": review["visual_review_complete"],
               "managed_exports": str(exports), "output_dir": str(output),
               "files": [{"path": str(output / Path(name).name), "managed_path": name} for name in final_paths],
               "downloads": {"pptx": deck["download_url"], "pdf": pdf["download_url"], "sources": code["download_url"], "kit": kit["download_url"]}}
    report = output / f"smoke_materials_{plan['plan_id']}.json"
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**summary, "report": str(report)}, ensure_ascii=False, indent=2))
    return 1 if review["status"] == "needs_revision" or (args.verify_code and verification["verification_status"] != "passed") else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", help="Also copy final deliverables here. Originals and download URLs stay in managed exports.")
    parser.add_argument("--verify-code", action="store_true", help="Explicitly compile/run this fixed Java example in a temporary workspace, without saving shell settings.")
    arguments = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(run(arguments)))
    except (RuntimeError, ValueError) as error:
        parser.exit(1, f"smoke_materials: {error}\n")
