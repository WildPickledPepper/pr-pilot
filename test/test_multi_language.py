# test/test_multi_language.py
"""
Unit tests for multi-language support: language registry, C/C++ parsing,
call graph building, and the parse_file_content dispatcher.
"""
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest


class TestLanguageRegistry(unittest.TestCase):
    """Tests for utils/language_registry.py"""

    def setUp(self):
        from utils.language_registry import LanguageRegistry
        self.reg = LanguageRegistry()

    def test_detect_python(self):
        lang = self.reg.detect_language("foo/bar.py")
        self.assertIsNotNone(lang)
        self.assertEqual(lang.name, "python")

    def test_detect_c(self):
        for ext in (".c", ".h"):
            lang = self.reg.detect_language(f"src/file{ext}")
            self.assertIsNotNone(lang, f"Failed for extension {ext}")
            self.assertEqual(lang.name, "c")

    def test_detect_cpp(self):
        for ext in (".cpp", ".cc", ".cxx", ".hpp", ".hxx"):
            lang = self.reg.detect_language(f"src/file{ext}")
            self.assertIsNotNone(lang, f"Failed for extension {ext}")
            self.assertEqual(lang.name, "cpp")

    def test_detect_java(self):
        lang = self.reg.detect_language("src/Main.java")
        self.assertIsNotNone(lang)
        self.assertEqual(lang.name, "java")
        self.assertIsNotNone(lang.grammar)

    def test_detect_go(self):
        lang = self.reg.detect_language("cmd/main.go")
        self.assertIsNotNone(lang)
        self.assertEqual(lang.name, "go")

    def test_detect_javascript(self):
        for ext in (".js", ".jsx", ".mjs"):
            lang = self.reg.detect_language(f"src/app{ext}")
            self.assertIsNotNone(lang, f"Failed for extension {ext}")
            self.assertEqual(lang.name, "javascript")

    def test_detect_typescript(self):
        for ext in (".ts", ".tsx"):
            lang = self.reg.detect_language(f"src/app{ext}")
            self.assertIsNotNone(lang, f"Failed for extension {ext}")
            self.assertEqual(lang.name, "typescript")

    def test_unsupported_returns_none(self):
        self.assertIsNone(self.reg.detect_language("readme.md"))
        self.assertIsNone(self.reg.detect_language("data.json"))

    def test_is_supported(self):
        self.assertTrue(self.reg.is_supported("a.py"))
        self.assertTrue(self.reg.is_supported("b.c"))
        self.assertTrue(self.reg.is_supported("c.cpp"))
        self.assertTrue(self.reg.is_supported("d.java"))
        self.assertTrue(self.reg.is_supported("e.go"))
        self.assertTrue(self.reg.is_supported("f.js"))
        self.assertTrue(self.reg.is_supported("g.ts"))
        self.assertTrue(self.reg.is_supported("h.rs"))
        self.assertTrue(self.reg.is_supported("i.rb"))
        self.assertTrue(self.reg.is_supported("j.php"))
        self.assertTrue(self.reg.is_supported("k.cs"))
        self.assertTrue(self.reg.is_supported("l.kt"))
        self.assertTrue(self.reg.is_supported("m.scala"))
        self.assertTrue(self.reg.is_supported("n.lua"))
        self.assertTrue(self.reg.is_supported("o.sh"))
        self.assertTrue(self.reg.is_supported("p.zig"))
        self.assertFalse(self.reg.is_supported("q.md"))
        self.assertFalse(self.reg.is_supported("r.yml"))

    def test_strip_extension(self):
        self.assertEqual(self.reg.strip_extension("src/main.py"), "src/main")
        self.assertEqual(self.reg.strip_extension("lib/inflate.c"), "lib/inflate")
        self.assertEqual(self.reg.strip_extension("include/fmt.hpp"), "include/fmt")
        # Unsupported extension is left as-is
        self.assertEqual(self.reg.strip_extension("readme.md"), "readme.md")

    def test_get_code_fence_tag(self):
        self.assertEqual(self.reg.get_code_fence_tag("a.py"), "python")
        self.assertEqual(self.reg.get_code_fence_tag("b.c"), "c")
        self.assertEqual(self.reg.get_code_fence_tag("c.cpp"), "cpp")
        self.assertEqual(self.reg.get_code_fence_tag("d.txt"), "")

    def test_get_all_extensions(self):
        exts = self.reg.get_all_extensions()
        self.assertIn(".py", exts)
        self.assertIn(".c", exts)
        self.assertIn(".h", exts)
        self.assertIn(".cpp", exts)
        self.assertIn(".java", exts)
        self.assertIn(".go", exts)
        self.assertIn(".js", exts)
        self.assertIn(".ts", exts)
        self.assertIn(".rs", exts)
        self.assertIn(".rb", exts)
        self.assertIn(".php", exts)
        self.assertIn(".cs", exts)
        self.assertIn(".kt", exts)
        self.assertIn(".kts", exts)
        self.assertIn(".scala", exts)
        self.assertIn(".lua", exts)
        self.assertIn(".sh", exts)
        self.assertIn(".bash", exts)
        self.assertIn(".zig", exts)

    def test_get_pmd_languages(self):
        pmd_langs = self.reg.get_pmd_languages()
        self.assertIn("python", pmd_langs)
        self.assertIn("c", pmd_langs)
        self.assertIn("cpp", pmd_langs)


class TestCCppParsing(unittest.TestCase):
    """Tests for C/C++ parsing via tree-sitter in code_parser.py"""

    def test_c_function_extraction(self):
        from utils.code_parser import parse_c_cpp_file_content

        c_code = """
int add(int a, int b) {
    return a + b;
}

void helper(void) {
    add(1, 2);
}

int main(int argc, char *argv[]) {
    helper();
    return 0;
}
"""
        results = parse_c_cpp_file_content(c_code, "test.c", "c")
        names = [r[0] for r in results]
        self.assertIn("add", names)
        self.assertIn("helper", names)
        self.assertIn("main", names)
        self.assertEqual(len(results), 3)

        # Verify line numbers
        for name, code, start, end in results:
            self.assertGreater(start, 0)
            self.assertGreaterEqual(end, start)
            self.assertIn(name, code)

    def test_cpp_class_method_extraction(self):
        from utils.code_parser import parse_c_cpp_file_content

        cpp_code = """
class MyClass {
public:
    void method_a() {
        // do something
    }
    int method_b(int x) {
        return x + 1;
    }
};

void free_func() {
    MyClass obj;
}
"""
        results = parse_c_cpp_file_content(cpp_code, "test.cpp", "cpp")
        names = [r[0] for r in results]

        self.assertIn("MyClass", names)           # The class itself
        self.assertIn("MyClass.method_a", names)   # Method
        self.assertIn("MyClass.method_b", names)   # Method
        self.assertIn("free_func", names)           # Free function

    def test_cpp_qualified_identifier(self):
        from utils.code_parser import parse_c_cpp_file_content

        cpp_code = """
class Foo {
public:
    int bar(int x);
};

int Foo::bar(int x) {
    return x * 2;
}
"""
        results = parse_c_cpp_file_content(cpp_code, "test.cpp", "cpp")
        names = [r[0] for r in results]
        # Foo::bar should be parsed as Foo.bar
        self.assertIn("Foo.bar", names)

    def test_empty_file(self):
        from utils.code_parser import parse_c_cpp_file_content
        results = parse_c_cpp_file_content("", "empty.c", "c")
        self.assertEqual(results, [])


class TestParseFileContentDispatcher(unittest.TestCase):
    """Tests for the parse_file_content() dispatcher"""

    def test_python_dispatch(self):
        from utils.code_parser import parse_file_content

        py_code = """
def hello():
    pass

class Foo:
    def bar(self):
        pass
"""
        results = parse_file_content(py_code, "test.py")
        names = [r[0] for r in results]
        self.assertIn("hello", names)
        self.assertIn("Foo", names)
        self.assertIn("Foo.bar", names)

    def test_c_dispatch(self):
        from utils.code_parser import parse_file_content

        c_code = "int main() { return 0; }\n"
        results = parse_file_content(c_code, "main.c")
        names = [r[0] for r in results]
        self.assertIn("main", names)

    def test_h_dispatch(self):
        from utils.code_parser import parse_file_content

        h_code = "void init(void) { }\n"
        results = parse_file_content(h_code, "init.h")
        names = [r[0] for r in results]
        self.assertIn("init", names)

    def test_cpp_dispatch(self):
        from utils.code_parser import parse_file_content

        cpp_code = "void run() { }\n"
        results = parse_file_content(cpp_code, "run.cpp")
        names = [r[0] for r in results]
        self.assertIn("run", names)

    def test_unsupported_returns_empty(self):
        from utils.code_parser import parse_file_content
        # Binary file extensions should return empty
        results = parse_file_content("some content", "data.png")
        self.assertEqual(results, [])


class TestCallgraphBuilder(unittest.TestCase):
    """Tests for the tree-sitter call graph builder"""

    def test_c_callgraph(self):
        import tempfile
        from utils.callgraph_builder import build_callgraph_tree_sitter

        c_code = """
int add(int a, int b) { return a + b; }
void helper(void) { add(1, 2); }
int main() { int r = add(3, 4); helper(); return 0; }
"""
        tmpfile = os.path.join(tempfile.gettempdir(), "test_cg.c")
        with open(tmpfile, "w") as f:
            f.write(c_code)

        graph = build_callgraph_tree_sitter([tmpfile], "c")

        # All functions should be in the graph
        self.assertEqual(len(graph), 3)

        # Find the main node
        main_node = [k for k in graph if k.endswith("__main")][0]
        add_node = [k for k in graph if k.endswith("__add")][0]
        helper_node = [k for k in graph if k.endswith("__helper")][0]

        # main calls add and helper
        self.assertIn(add_node, graph[main_node])
        self.assertIn(helper_node, graph[main_node])

        # helper calls add
        self.assertIn(add_node, graph[helper_node])

        # add calls nothing
        self.assertEqual(graph[add_node], [])

        os.unlink(tmpfile)

    def test_empty_file(self):
        import tempfile
        from utils.callgraph_builder import build_callgraph_tree_sitter

        tmpfile = os.path.join(tempfile.gettempdir(), "test_empty.c")
        with open(tmpfile, "w") as f:
            f.write("")

        graph = build_callgraph_tree_sitter([tmpfile], "c")
        self.assertEqual(graph, {})

        os.unlink(tmpfile)


class TestJavaParsing(unittest.TestCase):
    """Tests for Java parsing via tree-sitter"""

    def test_java_method_extraction(self):
        from utils.code_parser import parse_file_content

        java_code = """
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int multiply(int a, int b) {
        return a * b;
    }
}
"""
        results = parse_file_content(java_code, "Calculator.java")
        names = [r[0] for r in results]
        self.assertIn("Calculator", names)
        self.assertIn("Calculator.add", names)
        self.assertIn("Calculator.multiply", names)

    def test_java_interface_extraction(self):
        from utils.code_parser import parse_file_content

        java_code = """
public interface Greeter {
    void greet(String name);
}

public class HelloGreeter implements Greeter {
    public void greet(String name) {
        System.out.println("Hello " + name);
    }
}
"""
        results = parse_file_content(java_code, "Greeter.java")
        names = [r[0] for r in results]
        self.assertIn("Greeter", names)
        self.assertIn("HelloGreeter", names)
        self.assertIn("HelloGreeter.greet", names)

    def test_java_constructor(self):
        from utils.code_parser import parse_file_content

        java_code = """
public class Person {
    private String name;

    public Person(String name) {
        this.name = name;
    }

    public String getName() {
        return this.name;
    }
}
"""
        results = parse_file_content(java_code, "Person.java")
        names = [r[0] for r in results]
        self.assertIn("Person", names)
        self.assertIn("Person.Person", names)  # constructor
        self.assertIn("Person.getName", names)

    def test_java_callgraph(self):
        import tempfile
        from utils.callgraph_builder import build_callgraph_tree_sitter

        java_code = """
public class App {
    public int add(int a, int b) {
        return a + b;
    }

    public void run() {
        int result = add(1, 2);
    }
}
"""
        tmpfile = os.path.join(tempfile.gettempdir(), "App.java")
        with open(tmpfile, "w") as f:
            f.write(java_code)

        graph = build_callgraph_tree_sitter([tmpfile], "java")
        self.assertGreater(len(graph), 0)

        # run calls add
        run_node = [k for k in graph if "run" in k][0]
        add_node = [k for k in graph if "add" in k][0]
        self.assertIn(add_node, graph[run_node])

        os.unlink(tmpfile)


class TestGoParsing(unittest.TestCase):
    """Tests for Go parsing via tree-sitter"""

    def test_go_function_extraction(self):
        from utils.code_parser import parse_file_content

        go_code = """package main

import "fmt"

func add(a int, b int) int {
    return a + b
}

func main() {
    fmt.Println(add(1, 2))
}
"""
        results = parse_file_content(go_code, "main.go")
        names = [r[0] for r in results]
        self.assertIn("add", names)
        self.assertIn("main", names)

    def test_go_method_with_receiver(self):
        from utils.code_parser import parse_file_content

        go_code = """package server

type Server struct {
    Port int
}

func (s *Server) Start() {
    // start server
}

func (s *Server) Stop() {
    // stop server
}

func NewServer(port int) *Server {
    return &Server{Port: port}
}
"""
        results = parse_file_content(go_code, "server.go")
        names = [r[0] for r in results]
        self.assertIn("Server.Start", names)
        self.assertIn("Server.Stop", names)
        self.assertIn("NewServer", names)

    def test_go_callgraph(self):
        import tempfile
        from utils.callgraph_builder import build_callgraph_tree_sitter

        go_code = """package main

func helper() int {
    return 42
}

func main() {
    x := helper()
    _ = x
}
"""
        tmpfile = os.path.join(tempfile.gettempdir(), "main.go")
        with open(tmpfile, "w") as f:
            f.write(go_code)

        graph = build_callgraph_tree_sitter([tmpfile], "go")
        self.assertGreater(len(graph), 0)

        main_node = [k for k in graph if "main" in k and "helper" not in k][0]
        helper_node = [k for k in graph if "helper" in k][0]
        self.assertIn(helper_node, graph[main_node])

        os.unlink(tmpfile)


class TestJavaScriptParsing(unittest.TestCase):
    """Tests for JavaScript parsing via tree-sitter"""

    def test_js_function_extraction(self):
        from utils.code_parser import parse_file_content

        js_code = """
function greet(name) {
    return "Hello " + name;
}

function add(a, b) {
    return a + b;
}
"""
        results = parse_file_content(js_code, "utils.js")
        names = [r[0] for r in results]
        self.assertIn("greet", names)
        self.assertIn("add", names)

    def test_js_class_method_extraction(self):
        from utils.code_parser import parse_file_content

        js_code = """
class Calculator {
    add(a, b) {
        return a + b;
    }

    multiply(a, b) {
        return a * b;
    }
}
"""
        results = parse_file_content(js_code, "calc.js")
        names = [r[0] for r in results]
        self.assertIn("Calculator", names)
        self.assertIn("Calculator.add", names)
        self.assertIn("Calculator.multiply", names)

    def test_js_arrow_function(self):
        from utils.code_parser import parse_file_content

        js_code = """
const add = (a, b) => {
    return a + b;
};

function main() {
    return add(1, 2);
}
"""
        results = parse_file_content(js_code, "app.js")
        names = [r[0] for r in results]
        self.assertIn("add", names)
        self.assertIn("main", names)

    def test_js_callgraph(self):
        import tempfile
        from utils.callgraph_builder import build_callgraph_tree_sitter

        js_code = """
function helper() {
    return 42;
}

function main() {
    return helper();
}
"""
        tmpfile = os.path.join(tempfile.gettempdir(), "app.js")
        with open(tmpfile, "w") as f:
            f.write(js_code)

        graph = build_callgraph_tree_sitter([tmpfile], "javascript")
        self.assertGreater(len(graph), 0)

        main_node = [k for k in graph if "main" in k and "helper" not in k][0]
        helper_node = [k for k in graph if "helper" in k][0]
        self.assertIn(helper_node, graph[main_node])

        os.unlink(tmpfile)


class TestTypeScriptParsing(unittest.TestCase):
    """Tests for TypeScript parsing via tree-sitter"""

    def test_ts_function_extraction(self):
        from utils.code_parser import parse_file_content

        ts_code = """
function greet(name: string): string {
    return "Hello " + name;
}

function add(a: number, b: number): number {
    return a + b;
}
"""
        results = parse_file_content(ts_code, "utils.ts")
        names = [r[0] for r in results]
        self.assertIn("greet", names)
        self.assertIn("add", names)

    def test_ts_class_method_extraction(self):
        from utils.code_parser import parse_file_content

        ts_code = """
class UserService {
    private users: string[] = [];

    addUser(name: string): void {
        this.users.push(name);
    }

    getUsers(): string[] {
        return this.users;
    }
}
"""
        results = parse_file_content(ts_code, "service.ts")
        names = [r[0] for r in results]
        self.assertIn("UserService", names)
        self.assertIn("UserService.addUser", names)
        self.assertIn("UserService.getUsers", names)

    def test_ts_arrow_function(self):
        from utils.code_parser import parse_file_content

        ts_code = """
const multiply = (a: number, b: number): number => {
    return a * b;
};

function compute(): number {
    return multiply(3, 4);
}
"""
        results = parse_file_content(ts_code, "math.ts")
        names = [r[0] for r in results]
        self.assertIn("multiply", names)
        self.assertIn("compute", names)

    def test_ts_callgraph(self):
        import tempfile
        from utils.callgraph_builder import build_callgraph_tree_sitter

        ts_code = """
function validate(x: number): boolean {
    return x > 0;
}

function process(data: number): number {
    if (validate(data)) {
        return data * 2;
    }
    return 0;
}
"""
        tmpfile = os.path.join(tempfile.gettempdir(), "logic.ts")
        with open(tmpfile, "w") as f:
            f.write(ts_code)

        graph = build_callgraph_tree_sitter([tmpfile], "typescript")
        self.assertGreater(len(graph), 0)

        process_node = [k for k in graph if "process" in k][0]
        validate_node = [k for k in graph if "validate" in k][0]
        self.assertIn(validate_node, graph[process_node])

        os.unlink(tmpfile)


class TestNewLanguageDetection(unittest.TestCase):
    """Tests for detection of the 9 new Tier 1 languages."""

    def setUp(self):
        from utils.language_registry import LanguageRegistry
        self.reg = LanguageRegistry()

    def test_detect_rust(self):
        lang = self.reg.detect_language("src/main.rs")
        self.assertIsNotNone(lang)
        self.assertEqual(lang.name, "rust")
        self.assertEqual(lang.tree_sitter_language, "rust")

    def test_detect_ruby(self):
        lang = self.reg.detect_language("app/models/user.rb")
        self.assertIsNotNone(lang)
        self.assertEqual(lang.name, "ruby")

    def test_detect_php(self):
        lang = self.reg.detect_language("src/Controller.php")
        self.assertIsNotNone(lang)
        self.assertEqual(lang.name, "php")

    def test_detect_csharp(self):
        lang = self.reg.detect_language("src/Program.cs")
        self.assertIsNotNone(lang)
        self.assertEqual(lang.name, "csharp")

    def test_detect_kotlin(self):
        for ext in (".kt", ".kts"):
            lang = self.reg.detect_language(f"src/Main{ext}")
            self.assertIsNotNone(lang, f"Failed for extension {ext}")
            self.assertEqual(lang.name, "kotlin")

    def test_detect_scala(self):
        lang = self.reg.detect_language("src/App.scala")
        self.assertIsNotNone(lang)
        self.assertEqual(lang.name, "scala")

    def test_detect_lua(self):
        lang = self.reg.detect_language("scripts/init.lua")
        self.assertIsNotNone(lang)
        self.assertEqual(lang.name, "lua")

    def test_detect_bash(self):
        for ext in (".sh", ".bash"):
            lang = self.reg.detect_language(f"scripts/deploy{ext}")
            self.assertIsNotNone(lang, f"Failed for extension {ext}")
            self.assertEqual(lang.name, "bash")

    def test_detect_zig(self):
        lang = self.reg.detect_language("src/main.zig")
        self.assertIsNotNone(lang)
        self.assertEqual(lang.name, "zig")


class TestTier2Utilities(unittest.TestCase):
    """Tests for Tier 2 binary detection and text file candidate logic."""

    def setUp(self):
        from utils.language_registry import LanguageRegistry
        self.reg = LanguageRegistry()

    def test_binary_extension_detection(self):
        self.assertTrue(self.reg.is_binary_extension("image.png"))
        self.assertTrue(self.reg.is_binary_extension("archive.zip"))
        self.assertTrue(self.reg.is_binary_extension("font.woff2"))
        self.assertTrue(self.reg.is_binary_extension("data.sqlite3"))
        self.assertFalse(self.reg.is_binary_extension("readme.md"))
        self.assertFalse(self.reg.is_binary_extension("config.yml"))
        self.assertFalse(self.reg.is_binary_extension("main.py"))

    def test_text_file_candidate(self):
        # .md is not registered and not binary -> Tier 2 candidate
        self.assertTrue(self.reg.is_text_file_candidate("readme.md"))
        self.assertTrue(self.reg.is_text_file_candidate("config.yml"))
        self.assertTrue(self.reg.is_text_file_candidate("app.dart"))
        # .py is registered -> not a Tier 2 candidate (it's Tier 1)
        self.assertFalse(self.reg.is_text_file_candidate("main.py"))
        self.assertFalse(self.reg.is_text_file_candidate("main.rs"))
        # .png is binary -> not a candidate
        self.assertFalse(self.reg.is_text_file_candidate("image.png"))

    def test_pmd_languages_exclude_empty(self):
        pmd_langs = self.reg.get_pmd_languages()
        self.assertIn("python", pmd_langs)
        self.assertIn("ruby", pmd_langs)
        self.assertNotIn("", pmd_langs)
        # Rust, Bash, Zig have empty pmd_cpd_language -> should not appear
        # (they map to "" which is excluded)

    def test_get_tree_sitter_languages(self):
        ts_langs = self.reg.get_tree_sitter_languages()
        ts_names = [l.name for l in ts_langs]
        # Python uses ast, not tree-sitter
        self.assertNotIn("python", ts_names)
        # All tree-sitter languages should be present
        for name in ("c", "cpp", "java", "go", "javascript", "typescript",
                      "rust", "ruby", "php", "csharp", "kotlin", "scala",
                      "lua", "bash", "zig"):
            self.assertIn(name, ts_names)


class TestRustParsing(unittest.TestCase):
    """Tests for Rust parsing via tree-sitter"""

    def test_rust_function_extraction(self):
        from utils.code_parser import parse_file_content

        rust_code = """
fn add(a: i32, b: i32) -> i32 {
    a + b
}

fn main() {
    let result = add(1, 2);
}
"""
        results = parse_file_content(rust_code, "main.rs")
        names = [r[0] for r in results]
        self.assertIn("add", names)
        self.assertIn("main", names)

    def test_rust_impl_method_extraction(self):
        from utils.code_parser import parse_file_content

        rust_code = """
struct Point {
    x: f64,
    y: f64,
}

impl Point {
    fn new(x: f64, y: f64) -> Self {
        Point { x, y }
    }

    fn distance(&self) -> f64 {
        (self.x * self.x + self.y * self.y).sqrt()
    }
}
"""
        results = parse_file_content(rust_code, "point.rs")
        names = [r[0] for r in results]
        self.assertIn("Point", names)  # struct_item
        self.assertIn("Point.new", names)  # impl method
        self.assertIn("Point.distance", names)

    def test_rust_callgraph(self):
        import tempfile
        from utils.callgraph_builder import build_callgraph_tree_sitter

        rust_code = """
fn helper() -> i32 {
    42
}

fn main() {
    let x = helper();
}
"""
        tmpfile = os.path.join(tempfile.gettempdir(), "test_cg.rs")
        with open(tmpfile, "w") as f:
            f.write(rust_code)

        graph = build_callgraph_tree_sitter([tmpfile], "rust")
        self.assertGreater(len(graph), 0)

        main_node = [k for k in graph if "main" in k and "helper" not in k][0]
        helper_node = [k for k in graph if "helper" in k][0]
        self.assertIn(helper_node, graph[main_node])

        os.unlink(tmpfile)


class TestRubyParsing(unittest.TestCase):
    """Tests for Ruby parsing via tree-sitter"""

    def test_ruby_method_extraction(self):
        from utils.code_parser import parse_file_content

        ruby_code = """
class Calculator
  def add(a, b)
    a + b
  end

  def multiply(a, b)
    a * b
  end
end
"""
        results = parse_file_content(ruby_code, "calculator.rb")
        names = [r[0] for r in results]
        self.assertIn("Calculator", names)
        self.assertIn("Calculator.add", names)
        self.assertIn("Calculator.multiply", names)

    def test_ruby_free_method(self):
        from utils.code_parser import parse_file_content

        ruby_code = """
def greet(name)
  puts "Hello #{name}"
end
"""
        results = parse_file_content(ruby_code, "helper.rb")
        names = [r[0] for r in results]
        self.assertIn("greet", names)


class TestCSharpParsing(unittest.TestCase):
    """Tests for C# parsing via tree-sitter"""

    def test_csharp_method_extraction(self):
        from utils.code_parser import parse_file_content

        cs_code = """
namespace MyApp {
    class Calculator {
        public int Add(int a, int b) {
            return a + b;
        }
        public int Multiply(int a, int b) {
            return a * b;
        }
    }
}
"""
        results = parse_file_content(cs_code, "Calculator.cs")
        names = [r[0] for r in results]
        self.assertIn("Calculator", names)
        self.assertIn("Calculator.Add", names)
        self.assertIn("Calculator.Multiply", names)


class TestKotlinParsing(unittest.TestCase):
    """Tests for Kotlin parsing via tree-sitter"""

    def test_kotlin_function_extraction(self):
        from utils.code_parser import parse_file_content

        kt_code = """
fun add(a: Int, b: Int): Int {
    return a + b
}

class Calculator {
    fun multiply(a: Int, b: Int): Int {
        return a * b
    }
}
"""
        results = parse_file_content(kt_code, "Calculator.kt")
        names = [r[0] for r in results]
        self.assertIn("add", names)
        self.assertIn("Calculator", names)
        self.assertIn("Calculator.multiply", names)


class TestScalaParsing(unittest.TestCase):
    """Tests for Scala parsing via tree-sitter"""

    def test_scala_function_extraction(self):
        from utils.code_parser import parse_file_content

        scala_code = """
object Calculator {
  def add(a: Int, b: Int): Int = {
    a + b
  }
}

def helper(): Unit = {
  println(42)
}
"""
        results = parse_file_content(scala_code, "Calculator.scala")
        names = [r[0] for r in results]
        self.assertIn("Calculator", names)
        self.assertIn("Calculator.add", names)
        self.assertIn("helper", names)


class TestPhpParsing(unittest.TestCase):
    """Tests for PHP parsing via tree-sitter"""

    def test_php_function_extraction(self):
        from utils.code_parser import parse_file_content

        php_code = """<?php
class Calculator {
    public function add($a, $b) {
        return $a + $b;
    }
}

function helper() {
    echo "hi";
}
?>"""
        results = parse_file_content(php_code, "Calculator.php")
        names = [r[0] for r in results]
        self.assertIn("Calculator", names)
        self.assertIn("Calculator.add", names)
        self.assertIn("helper", names)


class TestLuaParsing(unittest.TestCase):
    """Tests for Lua parsing via tree-sitter"""

    def test_lua_function_extraction(self):
        from utils.code_parser import parse_file_content

        lua_code = """
function add(a, b)
    return a + b
end

function helper()
    print("hi")
end
"""
        results = parse_file_content(lua_code, "utils.lua")
        names = [r[0] for r in results]
        self.assertIn("add", names)
        self.assertIn("helper", names)


class TestBashParsing(unittest.TestCase):
    """Tests for Bash parsing via tree-sitter"""

    def test_bash_function_extraction(self):
        from utils.code_parser import parse_file_content

        bash_code = """
hello() {
    echo "hello"
}

function world {
    echo "world"
}
"""
        results = parse_file_content(bash_code, "deploy.sh")
        names = [r[0] for r in results]
        self.assertIn("hello", names)
        self.assertIn("world", names)


class TestZigParsing(unittest.TestCase):
    """Tests for Zig parsing via tree-sitter"""

    def test_zig_function_extraction(self):
        from utils.code_parser import parse_file_content

        zig_code = """
fn add(a: i32, b: i32) i32 {
    return a + b;
}

pub fn main() void {
    const result = add(1, 2);
}
"""
        results = parse_file_content(zig_code, "main.zig")
        names = [r[0] for r in results]
        self.assertIn("add", names)
        self.assertIn("main", names)


class TestTier2TextChunking(unittest.TestCase):
    """Tests for Tier 2 universal text file chunking"""

    def test_markdown_chunking(self):
        from utils.code_parser import parse_file_content

        md_content = """# Title

This is the first paragraph with some
content spanning multiple lines.

## Section 2

Another paragraph here with
different content.

## Section 3

Final section.
"""
        results = parse_file_content(md_content, "README.md")
        self.assertGreater(len(results), 0)
        # Each chunk should have proper (name, text, start, end)
        for name, text, start, end in results:
            self.assertGreater(start, 0)
            self.assertGreaterEqual(end, start)
            self.assertTrue(len(text) > 0)

    def test_yaml_chunking(self):
        from utils.code_parser import parse_file_content

        yaml_content = """name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: npm install
"""
        results = parse_file_content(yaml_content, "ci.yml")
        self.assertGreater(len(results), 0)

    def test_dart_chunking(self):
        from utils.code_parser import parse_file_content

        dart_content = """
void main() {
  print('Hello Dart');
}

class Calculator {
  int add(int a, int b) {
    return a + b;
  }
}
"""
        results = parse_file_content(dart_content, "main.dart")
        self.assertGreater(len(results), 0)

    def test_binary_file_returns_empty(self):
        from utils.code_parser import parse_file_content
        # .png is a binary extension -> should return empty
        results = parse_file_content("fake content", "image.png")
        self.assertEqual(results, [])

    def test_large_text_splitting(self):
        from utils.code_parser import parse_text_file_content

        # Create content with 100 lines
        lines = [f"line {i}" for i in range(100)]
        content = "\n".join(lines)
        results = parse_text_file_content(content, "big.txt")
        self.assertGreater(len(results), 1)
        # Verify no gap in coverage
        for name, text, start, end in results:
            self.assertGreater(start, 0)
            self.assertGreaterEqual(end, start)

    def test_empty_file(self):
        from utils.code_parser import parse_text_file_content
        results = parse_text_file_content("", "empty.txt")
        self.assertEqual(results, [])

    def test_registered_language_not_tier2(self):
        """Registered language files should NOT go through Tier 2 chunking."""
        from utils.code_parser import parse_file_content
        # .py is a registered language; even with invalid Python, it should
        # go through Python parser, not text chunker
        results = parse_file_content("def foo():\n    pass\n", "test.py")
        names = [r[0] for r in results]
        self.assertIn("foo", names)


if __name__ == "__main__":
    unittest.main()
