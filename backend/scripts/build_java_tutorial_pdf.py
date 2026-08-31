"""Generate the Java beginner tutorial PDF into backend/data/exports."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.agent.tools.export_urls import ascii_export_stem, export_download_url
from app.agent.tools.pdf_builder import build_pdf

SECTIONS = [
    {
        "heading": "这份讲义怎么用",
        "body": (
            "这是一份面向零基础读者的 Java 入门讲义，按「先能跑起来，再讲清楚为什么」编排。"
            "建议边读边在本机敲代码：装好 JDK 后，每一节的示例都可以单独保存为 .java 文件并编译运行。"
        ),
        "bullets": [
            "目标：能独立写出带类、方法和基本控制流的小程序",
            "时长：跟着敲大约 4–8 小时",
            "预备：一台电脑，会使用命令行即可，不要求有其他语言基础",
        ],
    },
    {
        "heading": "1. Java 是什么",
        "body": (
            "Java 是一种静态类型、面向对象的编程语言，由 Sun Microsystems 在 1995 年发布，现在由 Oracle 维护。"
            "它的核心承诺是「一次编写，到处运行」（Write Once, Run Anywhere）：源代码先编译成字节码（.class），"
            "再由各平台上的 Java 虚拟机（JVM）执行。"
        ),
        "bullets": [
            "跨平台：同一份 .class 可在 Windows / macOS / Linux 的 JVM 上运行",
            "面向对象：用类和对象组织代码，适合中大型项目",
            "生态成熟：Spring、Android、大数据（Hadoop/Spark）都大量使用 Java",
            "强类型 + 自动内存管理（垃圾回收），减少一类低级错误",
        ],
    },
    {
        "heading": "JDK、JRE、JVM",
        "level": 2,
        "body": "初学者最容易把这三个缩写混在一起。记住职责即可：",
        "bullets": [
            "JVM：运行字节码的虚拟机，是「执行引擎」",
            "JRE：JVM + 标准类库，用来「跑」Java 程序",
            "JDK：JRE + 编译器 javac 等开发工具，用来「写」Java 程序",
            "学习请安装 JDK（已包含运行环境），不要只装 JRE",
        ],
    },
    {
        "heading": "2. 安装与第一个程序",
        "body": (
            "到 Oracle 或 Adoptium（Eclipse Temurin）下载 JDK 17 或 21（长期支持版）。"
            "安装后在终端执行 java -version 与 javac -version，两者都能输出版本号即表示成功。"
            "Windows 若提示找不到命令，需要把 JDK 的 bin 目录加入 PATH。"
        ),
        "code": """public class HelloJava {
    public static void main(String[] args) {
        System.out.println("你好，Java");
    }
}""",
        "language": "java",
    },
    {
        "heading": "编译与运行",
        "level": 2,
        "body": (
            "把上面的代码保存为 HelloJava.java（文件名必须与 public class 同名）。"
            "然后在该目录执行："
        ),
        "code": """javac HelloJava.java
java HelloJava""",
        "language": "shell",
        "bullets": [
            "javac 生成 HelloJava.class（字节码）",
            "java HelloJava 由 JVM 加载并执行 main 方法",
            "main 是程序入口：签名必须是 public static void main(String[] args)",
        ],
    },
    {
        "heading": "3. 基础语法",
        "body": (
            "Java 语句以分号结尾；代码块用花括号 {}；大小写敏感。"
            "注释有三种：// 单行、/* 多行 */、/** 文档注释 */。"
            "标识符（类名、方法名、变量名）只能由字母、数字、下划线和 $ 组成，且不能以数字开头。"
        ),
        "bullets": [
            "类名用大驼峰：HelloJava、UserService",
            "方法与变量用小驼峰：printSum、userName",
            "常量全大写下划线：MAX_SIZE",
            "一个 .java 文件最多一个 public 类，且文件名与该类同名",
        ],
    },
    {
        "heading": "4. 数据类型与变量",
        "body": (
            "Java 把类型分成两大类：基本类型（存在栈上的值）和引用类型（对象，存在堆上，变量里存的是引用）。"
            "声明变量时必须写出类型：int count = 3;"
        ),
    },
    {
        "heading": "八种基本类型",
        "level": 2,
        "bullets": [
            "整数：byte / short / int / long（日常默认用 int，大数用 long 并加 L：10L）",
            "浮点：float（加 F）与 double（默认小数是 double）",
            "字符：char，单引号一个字符，如 'A'",
            "布尔：boolean，只有 true 和 false，不能与 0/1 互换",
        ],
        "code": """int age = 20;
double price = 19.9;
boolean ok = true;
char grade = 'A';
String name = "Ada";  // String 是引用类型，不是基本类型""",
        "language": "java",
    },
    {
        "heading": "常用运算",
        "level": 2,
        "bullets": [
            "算术：+ - * / %    注意整数相除会丢掉小数：7/2 结果是 3",
            "比较：== != > < >= <=    对象内容比较用 equals，不要用 == 比字符串",
            "逻辑：&& || !",
            "赋值与复合：=  +=  ++  --",
        ],
        "code": """String a = "hi";
String b = "hi";
System.out.println(a.equals(b));  // true，比的是内容
System.out.println(7 / 2);        // 3
System.out.println(7 / 2.0);      // 3.5""",
        "language": "java",
    },
    {
        "heading": "5. 控制流程",
        "body": "程序默认从上到下执行。条件与循环让它「会判断、会重复」。",
    },
    {
        "heading": "条件：if / else / switch",
        "level": 2,
        "code": """int score = 86;
if (score >= 90) {
    System.out.println("优秀");
} else if (score >= 60) {
    System.out.println("及格");
} else {
    System.out.println("不及格");
}

switch (score / 10) {
    case 10, 9 -> System.out.println("A");
    case 8 -> System.out.println("B");
    default -> System.out.println("C 或以下");
}""",
        "language": "java",
    },
    {
        "heading": "循环：for / while / 增强 for",
        "level": 2,
        "code": """for (int i = 0; i < 3; i++) {
    System.out.println("for: " + i);
}

int n = 3;
while (n > 0) {
    System.out.println("while: " + n);
    n--;
}

int[] nums = {1, 2, 3};
for (int x : nums) {
    System.out.println("each: " + x);
}""",
        "language": "java",
        "bullets": [
            "break 跳出当前循环；continue 跳过本轮剩余语句",
            "能确定次数用 for；条件驱动用 while；遍历数组/集合用增强 for",
        ],
    },
    {
        "heading": "6. 数组与方法",
        "body": (
            "数组长度固定，下标从 0 开始。方法把一段可复用逻辑起名，"
            "main 只负责调度，具体计算放到别的方法里，程序会清晰很多。"
        ),
        "code": """public class SumDemo {
    public static void main(String[] args) {
        int[] xs = {2, 4, 6};
        System.out.println(sum(xs));
    }

    static int sum(int[] xs) {
        int total = 0;
        for (int x : xs) {
            total += x;
        }
        return total;
    }
}""",
        "language": "java",
        "bullets": [
            "方法签名：返回类型 + 方法名 + 参数列表",
            "void 表示没有返回值",
            "static 方法属于类，可在不 new 对象时调用（入门示例常用）",
        ],
    },
    {
        "heading": "7. 面向对象入门",
        "body": (
            "类是模板，对象是模板造出来的实例。把「数据」和「操作这些数据的方法」放在同一个类里，"
            "就是封装。Java 程序几乎都从定义类开始。"
        ),
        "code": """public class Student {
    private String name;
    private int score;

    public Student(String name, int score) {
        this.name = name;
        this.score = score;
    }

    public boolean passed() {
        return score >= 60;
    }

    public String getName() {
        return name;
    }

    public static void main(String[] args) {
        Student s = new Student("林晚", 88);
        System.out.println(s.getName() + " 及格? " + s.passed());
    }
}""",
        "language": "java",
    },
    {
        "heading": "四个关键词",
        "level": 2,
        "bullets": [
            "封装：字段 private，通过方法读写，避免外部随便改内部状态",
            "继承：子类 extends 父类，复用并扩展行为（先会用，再追求继承树）",
            "多态：同样的方法调用，运行时走到不同子类的实现",
            "构造方法：与类同名、没有返回类型，new 时用来初始化对象",
        ],
    },
    {
        "heading": "8. 接下来学什么",
        "body": "入门之后不要急着上框架。按下面顺序补齐，会比直接跳进 Spring 稳得多。",
        "bullets": [
            "String、ArrayList、HashMap：日常处理文本和集合",
            "异常：try / catch / throw，先会处理失败再谈「优雅」",
            "文件与 IO：读写文本文件",
            "接口与抽象类：把「能做什么」和「怎么做」分开",
            "再学构建工具 Maven/Gradle，然后才是 Spring Boot",
            "练习建议：命令行待办、猜数字、简易通讯录——每个小项目用到类 + 集合 + 循环即可",
        ],
    },
    {
        "heading": "常见坑",
        "level": 2,
        "bullets": [
            "比较字符串用 equals，不要用 ==",
            "数组下标越界：长度是 n，合法下标是 0..n-1",
            "空指针 NullPointerException：调用方法前确认对象不是 null",
            "中文文件编码保存为 UTF-8，javac 必要时加 -encoding UTF-8",
        ],
    },
]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    export_dir = root / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    title = "Java 编程基础教程"
    filename = f"{ascii_export_stem(title, fallback='Java')}_{uuid.uuid4().hex[:12]}.pdf"
    path = export_dir / filename
    pages = build_pdf(
        path=path,
        title=title,
        subtitle="零基础入门讲义 · 语法 / 控制流 / 面向对象",
        sections=SECTIONS,
        brand="Nous",
    )
    print(path)
    print(f"pages={pages}")
    print(export_download_url(filename))


if __name__ == "__main__":
    main()
