"""Generate a designed Java basics teaching deck."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.agent.tools.builtins import create_presentation


HELLO = """public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, Java!");
    }
}"""

VARS = """public class Vars {
    public static void main(String[] args) {
        int age = 20;
        double score = 95.5;
        boolean ok = true;
        String name = "Nous";
        System.out.println(name + " / " + age);
    }
}"""

IF_FOR = """int score = 86;
if (score >= 90) {
    System.out.println("优秀");
} else if (score >= 60) {
    System.out.println("及格");
} else {
    System.out.println("不及格");
}

for (int i = 1; i <= 5; i++) {
    System.out.println("第 " + i + " 次");
}"""

ARRAY = """int[] nums = {3, 1, 4, 1, 5};
int sum = 0;
for (int n : nums) {
    sum += n;
}
System.out.println("sum=" + sum);
System.out.println("len=" + nums.length);"""

METHOD = """public class MathUtil {
    public static int add(int a, int b) {
        return a + b;
    }

    public static void main(String[] args) {
        int result = add(3, 5);
        System.out.println(result); // 8
    }
}"""

OOP = """public class Student {
    private String name;
    private int age;

    public Student(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public void introduce() {
        System.out.println(name + ", " + age);
    }
}"""

EXTENDS = """class Animal {
    void speak() {
        System.out.println("...");
    }
}

class Dog extends Animal {
    @Override
    void speak() {
        System.out.println("汪汪");
    }
}"""

EXC = """try {
    int x = Integer.parseInt("12a");
    System.out.println(x);
} catch (NumberFormatException e) {
    System.out.println("格式错误: " + e.getMessage());
} finally {
    System.out.println("清理收尾");
}"""


SLIDES = [
    {
        "layout": "title",
        "heading": "Java 编程基础精讲",
        "subtitle": "由浅入深 · 代码示例 + 要点讲解 · 适合零基础入门",
    },
    {
        "layout": "section",
        "heading": "认识 Java",
        "subtitle": "它是什么、能做什么、为什么先学它",
    },
    {
        "layout": "bullets",
        "heading": "Java 是什么",
        "bullets": [
            "一门面向对象的编程语言（Write Once, Run Anywhere）",
            "源码 .java → 编译成字节码 .class → JVM 跨平台运行",
            "广泛用于后端服务、安卓、大数据、中间件",
            "语法严谨、生态成熟，适合打下扎实编程基础",
        ],
    },
    {
        "layout": "two_column",
        "heading": "核心特点一览",
        "left_heading": "语言特性",
        "left_bullets": [
            "强类型、编译检查早报错",
            "面向对象：封装 / 继承 / 多态",
            "自动内存管理（GC）",
            "丰富的标准库",
        ],
        "right_heading": "学习路径建议",
        "right_bullets": [
            "语法基础 → 流程控制",
            "数组与方法",
            "类与对象",
            "异常与常用 API",
        ],
    },
    {
        "layout": "section",
        "heading": "第一个程序",
        "subtitle": "HelloWorld：理解入口、类与输出",
    },
    {
        "layout": "code",
        "heading": "HelloWorld 完整示例",
        "language": "java",
        "code": HELLO,
        "explain": [
            "public class 名称必须与文件名一致",
            "main 是程序入口，JVM 从这里启动",
            "String[] args 接收命令行参数",
            "println 输出并换行",
        ],
    },
    {
        "layout": "bullets",
        "heading": "编译与运行三步",
        "bullets": [
            "编写：HelloWorld.java",
            "编译：javac HelloWorld.java → 生成 HelloWorld.class",
            "运行：java HelloWorld（不要带 .class）",
            "常见坑：类名大小写不一致、没配 JAVA_HOME / PATH",
        ],
    },
    {
        "layout": "section",
        "heading": "数据类型与变量",
        "subtitle": "先把“盒子”选对，再往里放值",
    },
    {
        "layout": "cards",
        "heading": "八大基本类型（记忆版）",
        "cards": [
            {"label": "整数", "value": "byte/short\nint/long", "hint": "最常用 int"},
            {"label": "浮点", "value": "float\ndouble", "hint": "默认写 1.0 是 double"},
            {"label": "其他", "value": "char\nboolean", "hint": "字符 / 真假"},
            {"label": "引用", "value": "String 等", "hint": "不是基本类型"},
        ],
    },
    {
        "layout": "code",
        "heading": "变量声明与使用",
        "language": "java",
        "code": VARS,
        "explain": [
            "类型 变量名 = 初值",
            "String 是引用类型，用双引号",
            "命名：小驼峰 studentName",
            "先声明再使用，作用域看大括号",
        ],
    },
    {
        "layout": "two_column",
        "heading": "常用运算符",
        "left_heading": "算术 / 比较",
        "left_bullets": [
            "+ - * / %",
            "注意：整数除法 5/2=2",
            "== != > < >= <=",
            "字符串比较用 equals()",
        ],
        "right_heading": "逻辑 / 赋值",
        "right_bullets": [
            "&& || ! （短路）",
            "+= -= *= /=",
            "++i / i++ 有先后差异",
            "三元：cond ? a : b",
        ],
    },
    {
        "layout": "section",
        "heading": "控制流程",
        "subtitle": "条件分支与循环：让程序“会做判断”",
    },
    {
        "layout": "code",
        "heading": "if / else 与 for 循环",
        "language": "java",
        "code": IF_FOR,
        "explain": [
            "条件必须是 boolean",
            "else if 可串联多个分支",
            "for 适合次数明确的循环",
            "还有 while / do-while",
        ],
    },
    {
        "layout": "bullets",
        "heading": "循环控制关键词",
        "bullets": [
            "break：立刻跳出当前循环",
            "continue：跳过本轮，进入下一轮",
            "嵌套循环时，break 只影响最内层（除非用标签）",
            "优先写清晰条件，少用“魔法数字”",
        ],
    },
    {
        "layout": "section",
        "heading": "数组与方法",
        "subtitle": "数据成组存放，逻辑提炼成可复用函数",
    },
    {
        "layout": "code",
        "heading": "数组遍历求与",
        "language": "java",
        "code": ARRAY,
        "explain": [
            "下标从 0 开始",
            "length 是字段不是方法",
            "增强 for：for (int n : nums)",
            "越界会抛 ArrayIndexOutOfBounds",
        ],
    },
    {
        "layout": "code",
        "heading": "方法：定义、调用、返回值",
        "language": "java",
        "code": METHOD,
        "explain": [
            "格式：返回类型 方法名(参数)",
            "void 表示无返回值",
            "static 方法可用 类名.方法 调用",
            "参数是局部变量，注意值传递",
        ],
    },
    {
        "layout": "section",
        "heading": "面向对象入门",
        "subtitle": "用类描述事物，用对象承载状态与行为",
    },
    {
        "layout": "code",
        "heading": "类、字段、构造、方法",
        "language": "java",
        "code": OOP,
        "explain": [
            "class 是模板，new 才得到对象",
            "private 保护内部数据（封装）",
            "构造方法名=类名，无返回类型",
            "this 指向当前对象",
        ],
    },
    {
        "layout": "code",
        "heading": "继承与方法重写",
        "language": "java",
        "code": EXTENDS,
        "explain": [
            "extends 表示“是一种”",
            "@Override 明确重写父方法",
            "多态：父类引用指向子类对象",
            "先掌握继承，再深入接口",
        ],
    },
    {
        "layout": "two_column",
        "heading": "三大特性速记",
        "left_heading": "封装 / 继承",
        "left_bullets": [
            "封装：隐藏细节，开放必要接口",
            "继承：复用父类，扩展新行为",
            "访问修饰：public/protected/默认/private",
        ],
        "right_heading": "多态",
        "right_bullets": [
            "同一调用，不同实现",
            "编译看左边，运行看右边",
            "配合抽象类 / 接口更灵活",
        ],
    },
    {
        "layout": "section",
        "heading": "异常处理入门",
        "subtitle": "程序难免出错，要优雅地接住并处理",
    },
    {
        "layout": "code",
        "heading": "try / catch / finally",
        "language": "java",
        "code": EXC,
        "explain": [
            "try：可能出错的代码",
            "catch：按类型捕获异常",
            "finally：无论成败都会执行",
            "先具体异常，后笼统 Exception",
        ],
    },
    {
        "layout": "cards",
        "heading": "学习检查清单",
        "cards": [
            {"label": "环境", "value": "JDK\n+ IDE", "hint": "会编译运行"},
            {"label": "语法", "value": "类型\n流程", "hint": "能写小练习"},
            {"label": "结构", "value": "方法\n数组", "hint": "会拆分逻辑"},
            {"label": "OO", "value": "类与\n对象", "hint": "会建简单模型"},
        ],
    },
    {
        "layout": "bullets",
        "heading": "接下来怎么练",
        "bullets": [
            "每天写 1 个小练习：猜数字、成绩统计、简易通讯录",
            "读懂报错信息，比死记语法更快进步",
            "先正确，再追求简洁；先能跑，再重构",
            "下一阶段：集合框架、IO、多线程、Spring 入门",
        ],
    },
    {
        "layout": "quote",
        "quote": "代码是写给人看的，只是顺便让机器能执行。",
        "attribution": "编程实践箴言",
    },
    {
        "layout": "closing",
        "heading": "开始写第一行 Java 吧",
        "subtitle": "Nous · Java 编程基础精讲",
    },
]


async def main() -> None:
    # title-only should no longer TypeError
    bad = await create_presentation(title="only-title")
    assert bad.get("ok") is False
    assert "slides" in (bad.get("error") or "").lower()

    result = await create_presentation(
        title="Java 编程基础精讲",
        subtitle="由浅入深 · 代码示例 + 详解",
        theme="slate",
        slides=SLIDES,
    )
    print(json.dumps({k: result.get(k) for k in ("ok", "slide_count", "theme", "download_url", "filename", "error")}, ensure_ascii=False, indent=2))
    if result.get("path"):
        print("path", result["path"])
        print("size", Path(result["path"]).stat().st_size)


if __name__ == "__main__":
    asyncio.run(main())
