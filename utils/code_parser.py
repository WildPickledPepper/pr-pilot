import ast
import os
from typing import List, Tuple

from utils.language_registry import registry

def parse_python_file(file_path: str) -> List[Tuple[str, str]]:
    """
    Parses a Python file and extracts top-level functions and classes.

    Args:
        file_path: The path to the Python file.

    Returns:
        A list of tuples, where each tuple contains (name, source_code).
        Example: [('my_function', 'def my_function(a, b):...'), ('MyClass', 'class MyClass:...')].
    """
    if not os.path.exists(file_path):
        return []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    chunks = []
    try:
        tree = ast.parse(content)
        for node in ast.iter_child_nodes(tree):
            # 我们只关心顶层的函数和类定义
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                chunk_name = node.name
                chunk_code = ast.get_source_segment(content, node)
                if chunk_code:
                    chunks.append((chunk_name, chunk_code))
    except Exception as e:
        print(f"Error parsing file {file_path}: {e}")

    return chunks

# 返回值: list[tuple[str, str, int, int]] -> (name, code, start_line, end_line)
def parse_python_file_content(content: str, file_path_for_logging: str) -> List[Tuple[str, str, int, int]]:
    """
    解析传入的字符串内容，递归提取函数/类及类方法的名称、源码、起止行号。
    类方法的命名格式为 ClassName.method_name，与 pyan 调用图的节点名对齐。
    """
    chunks = []
    try:
        tree = ast.parse(content)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                chunk_code = ast.get_source_segment(content, node)
                if chunk_code and node.lineno and node.end_lineno:
                    chunks.append((node.name, chunk_code, node.lineno, node.end_lineno))

            elif isinstance(node, ast.ClassDef):
                # 先添加整个类
                class_code = ast.get_source_segment(content, node)
                if class_code and node.lineno and node.end_lineno:
                    chunks.append((node.name, class_code, node.lineno, node.end_lineno))

                # 再递归提取类内部的方法
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.FunctionDef):
                        method_code = ast.get_source_segment(content, child)
                        method_name = f"{node.name}.{child.name}"
                        if method_code and child.lineno and child.end_lineno:
                            chunks.append((method_name, method_code, child.lineno, child.end_lineno))
    except Exception as e:
        print(f"Error parsing content from {file_path_for_logging}: {e}")
    return chunks


# --- tree-sitter based C/C++ parsing ---

def _get_ts_parser(language_name: str):
    """Get a tree-sitter Parser for the given language."""
    from tree_sitter import Language, Parser
    if language_name == "c":
        import tree_sitter_c
        lang = Language(tree_sitter_c.language())
    elif language_name == "cpp":
        import tree_sitter_cpp
        lang = Language(tree_sitter_cpp.language())
    elif language_name == "java":
        import tree_sitter_java
        lang = Language(tree_sitter_java.language())
    elif language_name == "go":
        import tree_sitter_go
        lang = Language(tree_sitter_go.language())
    elif language_name == "javascript":
        import tree_sitter_javascript
        lang = Language(tree_sitter_javascript.language())
    elif language_name == "typescript":
        import tree_sitter_typescript
        lang = Language(tree_sitter_typescript.language_typescript())
    else:
        raise ValueError(f"No tree-sitter grammar for language: {language_name}")
    return Parser(lang)


def _get_function_name_from_declarator(declarator_node) -> str:
    """Extract the function name from a function_declarator node.

    Handles:
    - Simple: identifier (e.g. 'main')
    - C++ class method inline: field_identifier (e.g. 'method_a')
    - C++ qualified: qualified_identifier (e.g. 'MyClass::method_b')
    """
    for child in declarator_node.children:
        if child.type == "identifier":
            return child.text.decode()
        if child.type == "field_identifier":
            return child.text.decode()
        if child.type == "qualified_identifier":
            # e.g. MyClass::method_b -> "MyClass.method_b"
            parts = []
            for qchild in child.children:
                if qchild.type in ("namespace_identifier", "identifier", "type_identifier"):
                    parts.append(qchild.text.decode())
            return ".".join(parts) if parts else child.text.decode()
        # Sometimes the declarator wraps another declarator (pointer_declarator, etc.)
        if child.type == "function_declarator":
            return _get_function_name_from_declarator(child)
    return ""


def _extract_functions_c_cpp(node, content_bytes: bytes, class_name: str = "") -> List[Tuple[str, str, int, int]]:
    """Recursively extract function definitions from a tree-sitter parse tree.

    Returns list of (name, source_code, start_line, end_line).
    Lines are 1-indexed.
    """
    results = []

    for child in node.children:
        if child.type == "function_definition":
            # Find the function_declarator child
            func_name = ""
            for fc in child.children:
                if fc.type == "function_declarator":
                    func_name = _get_function_name_from_declarator(fc)
                    break

            if not func_name:
                continue

            # If we're inside a class, prefix with class name
            if class_name and "." not in func_name:
                func_name = f"{class_name}.{func_name}"

            start_line = child.start_point[0] + 1  # tree-sitter is 0-indexed
            end_line = child.end_point[0] + 1
            source = content_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
            results.append((func_name, source, start_line, end_line))

        elif child.type in ("class_specifier", "struct_specifier"):
            # Extract class/struct name and recurse into its field_declaration_list
            cname = ""
            for cc in child.children:
                if cc.type in ("type_identifier", "identifier"):
                    cname = cc.text.decode()
                    break

            # Also add the whole class as a chunk
            start_line = child.start_point[0] + 1
            end_line = child.end_point[0] + 1
            class_source = content_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
            if cname:
                results.append((cname, class_source, start_line, end_line))

            # Recurse into field_declaration_list to find inline methods
            for cc in child.children:
                if cc.type == "field_declaration_list":
                    results.extend(_extract_functions_c_cpp(cc, content_bytes, class_name=cname or class_name))

        elif child.type == "namespace_definition":
            # Recurse into namespace body
            for cc in child.children:
                if cc.type == "declaration_list":
                    results.extend(_extract_functions_c_cpp(cc, content_bytes, class_name=class_name))

    return results


def parse_c_cpp_file_content(content: str, file_path: str, language: str = "c") -> List[Tuple[str, str, int, int]]:
    """Parse C/C++ file content using tree-sitter.

    Args:
        content: Source code as string.
        file_path: File path (for logging).
        language: "c" or "cpp".

    Returns:
        List of (name, source_code, start_line, end_line) tuples.
    """
    try:
        parser = _get_ts_parser(language)
        content_bytes = content.encode("utf-8")
        tree = parser.parse(content_bytes)
        return _extract_functions_c_cpp(tree.root_node, content_bytes)
    except Exception as e:
        print(f"Error parsing C/C++ content from {file_path}: {e}")
        return []


# --- Generic tree-sitter extraction (data-driven by TreeSitterGrammar) ---

def _get_name_by_field(node) -> str:
    """Extract function/method name using child_by_field_name('name').
    Works for Java, Go, JavaScript, TypeScript, and most languages.
    """
    name_node = node.child_by_field_name("name")
    if name_node:
        return name_node.text.decode()
    return ""


def _get_go_receiver_type(node) -> str:
    """Extract receiver type from a Go method_declaration.
    e.g. `func (s *Server) Start()` -> 'Server'
    """
    params_node = node.child_by_field_name("receiver")
    if params_node is None:
        # Try finding parameter_list child (receiver parameters)
        for child in node.children:
            if child.type == "parameter_list":
                params_node = child
                break
    if params_node is None:
        return ""
    # The parameter_list contains a parameter_declaration with a type
    for child in params_node.children:
        if child.type == "parameter_declaration":
            type_node = child.child_by_field_name("type")
            if type_node:
                # Could be pointer_type (*Server) or just type_identifier (Server)
                if type_node.type == "pointer_type":
                    for tc in type_node.children:
                        if tc.type == "type_identifier":
                            return tc.text.decode()
                elif type_node.type == "type_identifier":
                    return type_node.text.decode()
    return ""


def _extract_functions_generic(node, content_bytes: bytes, grammar, class_name: str = "") -> List[Tuple[str, str, int, int]]:
    """Generic recursive extraction of functions/classes using a TreeSitterGrammar config.

    Returns list of (name, source_code, start_line, end_line).
    """
    results = []

    for child in node.children:
        # Handle function definitions
        if child.type in grammar.function_types:
            if grammar.name_strategy == "field_name":
                func_name = _get_name_by_field(child)
            else:
                # "declarator" strategy (C/C++) — should not reach here for generic path
                func_name = _get_name_by_field(child)

            # Go method_declaration: prefix with receiver type
            if child.type == "method_declaration" and not class_name:
                receiver_type = _get_go_receiver_type(child)
                if receiver_type and func_name:
                    func_name = f"{receiver_type}.{func_name}"
            elif class_name and func_name:
                func_name = f"{class_name}.{func_name}"

            # JS/TS arrow_function: name comes from parent variable_declarator
            if not func_name and child.type == "arrow_function":
                if node.type == "variable_declarator":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        func_name = name_node.text.decode()
                        if class_name:
                            func_name = f"{class_name}.{func_name}"

            if not func_name:
                continue

            start_line = child.start_point[0] + 1
            end_line = child.end_point[0] + 1
            source = content_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
            results.append((func_name, source, start_line, end_line))

        # Handle class/interface/enum definitions
        elif child.type in grammar.class_types:
            cname = ""
            for cc in child.children:
                if cc.type == grammar.class_name_type:
                    cname = cc.text.decode()
                    break

            # Add the whole class as a chunk
            start_line = child.start_point[0] + 1
            end_line = child.end_point[0] + 1
            class_source = content_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
            if cname:
                results.append((cname, class_source, start_line, end_line))

            # Recurse into class body
            for cc in child.children:
                if cc.type == grammar.class_body_type:
                    results.extend(_extract_functions_generic(cc, content_bytes, grammar, class_name=cname or class_name))

        # Handle namespace/module containers
        elif child.type in grammar.container_types:
            for cc in child.children:
                if cc.type == "declaration_list":
                    results.extend(_extract_functions_generic(cc, content_bytes, grammar, class_name=class_name))

        # JS/TS: variable declarations may contain arrow functions
        elif child.type in ("lexical_declaration", "variable_declaration"):
            for declarator in child.children:
                if declarator.type == "variable_declarator":
                    # Check if value is an arrow_function
                    value_node = declarator.child_by_field_name("value")
                    if value_node and value_node.type == "arrow_function":
                        var_name = ""
                        name_node = declarator.child_by_field_name("name")
                        if name_node:
                            var_name = name_node.text.decode()
                        if class_name and var_name:
                            var_name = f"{class_name}.{var_name}"
                        if var_name:
                            start_line = child.start_point[0] + 1
                            end_line = child.end_point[0] + 1
                            source = content_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                            results.append((var_name, source, start_line, end_line))

        # For export statements (JS/TS), recurse into child
        elif child.type in ("export_statement",):
            results.extend(_extract_functions_generic(child, content_bytes, grammar, class_name=class_name))

    return results


def parse_generic_file_content(content: str, file_path: str, language: str, grammar) -> List[Tuple[str, str, int, int]]:
    """Parse file content using the generic tree-sitter extraction.

    Args:
        content: Source code as string.
        file_path: File path (for logging).
        language: tree-sitter language name.
        grammar: TreeSitterGrammar config.

    Returns:
        List of (name, source_code, start_line, end_line) tuples.
    """
    try:
        parser = _get_ts_parser(language)
        content_bytes = content.encode("utf-8")
        tree = parser.parse(content_bytes)
        return _extract_functions_generic(tree.root_node, content_bytes, grammar)
    except Exception as e:
        print(f"Error parsing {language} content from {file_path}: {e}")
        return []


def parse_file_content(content: str, file_path: str) -> List[Tuple[str, str, int, int]]:
    """Dispatcher: route to the correct parser based on file extension.

    Returns list of (name, source_code, start_line, end_line).
    """
    lang_config = registry.detect_language(file_path)
    if lang_config is None:
        return []

    if lang_config.name == "python":
        return parse_python_file_content(content, file_path)
    elif lang_config.name in ("c", "cpp"):
        # C/C++ use the specialized declarator-based parser
        return parse_c_cpp_file_content(content, file_path, lang_config.tree_sitter_language)
    elif lang_config.grammar and lang_config.tree_sitter_language:
        # All other languages use the generic grammar-driven parser
        return parse_generic_file_content(content, file_path, lang_config.tree_sitter_language, lang_config.grammar)
    else:
        return []