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
        self.assertFalse(self.reg.is_supported("h.rs"))

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
        results = parse_file_content("some content", "data.json")
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


if __name__ == "__main__":
    unittest.main()
