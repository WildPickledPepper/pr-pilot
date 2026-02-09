# utils/callgraph_builder.py
"""
Tree-sitter based call graph builder for C/C++ and generic languages.
Outputs an adjacency list Dict[str, List[str]] compatible with graph_parser.parse_dot_file().
"""
import os
import json
from typing import Dict, List
from utils.code_parser import _get_ts_parser, _get_name_by_field, _get_go_receiver_type
from utils.language_registry import registry


def _collect_call_expressions(node, known_functions: set) -> List[str]:
    """Recursively find all call_expression nodes and return callee names."""
    calls = []
    for child in node.children:
        if child.type == "call_expression":
            # The first child of a call_expression is the function being called
            callee_node = child.children[0] if child.children else None
            if callee_node:
                if callee_node.type == "identifier":
                    callee = callee_node.text.decode()
                    if callee in known_functions:
                        calls.append(callee)
                elif callee_node.type == "qualified_identifier":
                    # e.g. MyClass::method -> MyClass.method
                    parts = []
                    for qc in callee_node.children:
                        if qc.type in ("namespace_identifier", "identifier", "type_identifier"):
                            parts.append(qc.text.decode())
                    callee = ".".join(parts)
                    if callee in known_functions:
                        calls.append(callee)
                elif callee_node.type == "field_expression":
                    # e.g. obj.method() or obj->method() — extract the method name
                    field_node = callee_node.child_by_field_name("field")
                    if field_node:
                        callee = field_node.text.decode()
                        # Try matching as a plain name or any Class.method
                        if callee in known_functions:
                            calls.append(callee)
                        else:
                            for kf in known_functions:
                                if kf.endswith(f".{callee}"):
                                    calls.append(kf)
                                    break
        # Recurse into children (but skip the call_expression's own children
        # since we already processed it above — we still need to recurse for nested calls)
        calls.extend(_collect_call_expressions(child, known_functions))
    return calls


def _get_func_name_from_declarator(declarator_node, class_name: str = "") -> str:
    """Extract function name from a function_declarator, with optional class prefix."""
    for child in declarator_node.children:
        if child.type == "identifier":
            name = child.text.decode()
            return f"{class_name}.{name}" if class_name else name
        if child.type == "field_identifier":
            name = child.text.decode()
            return f"{class_name}.{name}" if class_name else name
        if child.type == "qualified_identifier":
            parts = []
            for qc in child.children:
                if qc.type in ("namespace_identifier", "identifier", "type_identifier"):
                    parts.append(qc.text.decode())
            return ".".join(parts)
    return ""


def _collect_functions_and_bodies(node, content_bytes: bytes, class_name: str = "") -> List[dict]:
    """Collect all function definitions with their names and body nodes.

    Returns list of dicts: {"name": str, "file_stem": str, "body_node": Node}
    """
    results = []
    for child in node.children:
        if child.type == "function_definition":
            for fc in child.children:
                if fc.type == "function_declarator":
                    name = _get_func_name_from_declarator(fc, class_name)
                    if name:
                        # Find compound_statement (body)
                        body = None
                        for bc in child.children:
                            if bc.type == "compound_statement":
                                body = bc
                                break
                        results.append({"name": name, "body_node": body})
                    break

        elif child.type in ("class_specifier", "struct_specifier"):
            cname = ""
            for cc in child.children:
                if cc.type in ("type_identifier", "identifier"):
                    cname = cc.text.decode()
                    break
            for cc in child.children:
                if cc.type == "field_declaration_list":
                    results.extend(_collect_functions_and_bodies(cc, content_bytes, class_name=cname or class_name))

        elif child.type == "namespace_definition":
            for cc in child.children:
                if cc.type == "declaration_list":
                    results.extend(_collect_functions_and_bodies(cc, content_bytes, class_name=class_name))

    return results


def _collect_functions_and_bodies_generic(node, content_bytes: bytes, grammar, class_name: str = "") -> List[dict]:
    """Collect function definitions with names and body nodes using grammar config.

    Returns list of dicts: {"name": str, "body_node": Node}
    """
    results = []
    for child in node.children:
        if child.type in grammar.function_types:
            name = _get_name_by_field(child)

            # Go method_declaration: prefix with receiver type
            if child.type == "method_declaration" and not class_name:
                receiver_type = _get_go_receiver_type(child)
                if receiver_type and name:
                    name = f"{receiver_type}.{name}"
            elif class_name and name:
                name = f"{class_name}.{name}"

            # JS/TS arrow_function in variable_declarator
            if not name and child.type == "arrow_function":
                if node.type == "variable_declarator":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        name = name_node.text.decode()
                        if class_name:
                            name = f"{class_name}.{name}"

            if name:
                body = None
                for bc in child.children:
                    if bc.type == grammar.function_body_type:
                        body = bc
                        break
                results.append({"name": name, "body_node": body})

        elif child.type in grammar.class_types:
            cname = ""
            for cc in child.children:
                if cc.type == grammar.class_name_type:
                    cname = cc.text.decode()
                    break
            for cc in child.children:
                if cc.type == grammar.class_body_type:
                    results.extend(_collect_functions_and_bodies_generic(
                        cc, content_bytes, grammar, class_name=cname or class_name))

        elif child.type in grammar.container_types:
            for cc in child.children:
                if cc.type == "declaration_list":
                    results.extend(_collect_functions_and_bodies_generic(
                        cc, content_bytes, grammar, class_name=class_name))

        # JS/TS: variable declarations with arrow functions
        elif child.type in ("lexical_declaration", "variable_declaration"):
            for declarator in child.children:
                if declarator.type == "variable_declarator":
                    value_node = declarator.child_by_field_name("value")
                    if value_node and value_node.type == "arrow_function":
                        var_name = ""
                        name_node = declarator.child_by_field_name("name")
                        if name_node:
                            var_name = name_node.text.decode()
                        if class_name and var_name:
                            var_name = f"{class_name}.{var_name}"
                        if var_name:
                            body = None
                            for bc in value_node.children:
                                if bc.type == grammar.function_body_type:
                                    body = bc
                                    break
                            results.append({"name": var_name, "body_node": body})

        elif child.type in ("export_statement",):
            results.extend(_collect_functions_and_bodies_generic(
                child, content_bytes, grammar, class_name=class_name))

    return results


def _collect_calls_generic(body_node, grammar, known_short_names: set) -> List[str]:
    """Recursively find call nodes and return short callee names using grammar config."""
    calls = []
    for child in body_node.children:
        if child.type in grammar.call_types:
            callee_name = _resolve_callee_name_generic(child, grammar)
            if callee_name:
                if callee_name in known_short_names:
                    calls.append(callee_name)
                else:
                    # Try suffix matching: "add" -> "App.add"
                    for kn in known_short_names:
                        if kn.endswith(f".{callee_name}"):
                            calls.append(kn)
                            break
        calls.extend(_collect_calls_generic(child, grammar, known_short_names))
    return calls


def _resolve_callee_name_generic(call_node, grammar) -> str:
    """Resolve callee name from a call/invocation node for any language."""
    if call_node.type == "method_invocation":
        # Java: method_invocation has "name" field for the method name
        name_node = call_node.child_by_field_name("name")
        if name_node:
            return name_node.text.decode()
        return ""

    # call_expression: first child is callee
    callee_node = call_node.children[0] if call_node.children else None
    if callee_node is None:
        return ""

    if callee_node.type == "identifier":
        return callee_node.text.decode()
    if callee_node.type == "qualified_identifier":
        parts = []
        for c in callee_node.children:
            if c.type in ("namespace_identifier", "identifier", "type_identifier"):
                parts.append(c.text.decode())
        return ".".join(parts)
    if callee_node.type in ("field_expression", "member_expression"):
        # obj.method() or obj->method()
        field_node = callee_node.child_by_field_name("field") or callee_node.child_by_field_name("property")
        if field_node:
            return field_node.text.decode()
    if callee_node.type == "selector_expression":
        # Go: pkg.Func() — the field is the function name
        field_node = callee_node.child_by_field_name("field")
        if field_node:
            return field_node.text.decode()
    return ""


def build_callgraph_tree_sitter(file_paths: List[str], language: str) -> Dict[str, List[str]]:
    """Build a call graph from source files using tree-sitter.

    Args:
        file_paths: List of source file paths.
        language: tree-sitter language name (e.g. "c", "cpp", "java", "go", etc.).

    Returns:
        Adjacency list: {caller: [callee1, callee2, ...]}
        All nodes (including those with no outgoing edges) are present as keys.
    """
    # Determine if we should use the generic grammar-driven path
    lang_config = registry.get_language(language)
    grammar = lang_config.grammar if lang_config else None
    use_generic = grammar is not None and language not in ("c", "cpp")

    parser = _get_ts_parser(language)
    all_functions = []
    known_function_names = set()

    # Pass 1: Collect all function definitions
    for fpath in file_paths:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            content_bytes = content.encode("utf-8")
            tree = parser.parse(content_bytes)

            file_stem = os.path.splitext(os.path.basename(fpath))[0]
            if use_generic:
                funcs = _collect_functions_and_bodies_generic(tree.root_node, content_bytes, grammar)
            else:
                funcs = _collect_functions_and_bodies(tree.root_node, content_bytes)

            for func_info in funcs:
                qualified = f"{file_stem}__{func_info['name'].replace('.', '__')}"
                func_info["qualified_name"] = qualified
                known_function_names.add(qualified)
                func_info["short_name"] = func_info["name"]
                all_functions.append(func_info)
        except Exception as e:
            print(f"  Warning: Could not parse {fpath} for call graph: {e}")

    # Build mapping from short names to qualified names
    short_to_qualified: Dict[str, List[str]] = {}
    for func_info in all_functions:
        short = func_info["short_name"]
        if short not in short_to_qualified:
            short_to_qualified[short] = []
        short_to_qualified[short].append(func_info["qualified_name"])

    # Pass 2: For each function body, find call expressions
    graph: Dict[str, List[str]] = {fi["qualified_name"]: [] for fi in all_functions}
    all_short_names = set(short_to_qualified.keys())

    for func_info in all_functions:
        if func_info["body_node"] is None:
            continue

        if use_generic:
            calls = _collect_calls_generic(func_info["body_node"], grammar, all_short_names)
        else:
            calls = _collect_call_expressions_simple(func_info["body_node"], all_short_names)
        caller_q = func_info["qualified_name"]

        for callee_short in calls:
            for callee_q in short_to_qualified.get(callee_short, []):
                if callee_q != caller_q and callee_q not in graph[caller_q]:
                    graph[caller_q].append(callee_q)

    return graph


def _collect_call_expressions_simple(node, known_short_names: set) -> List[str]:
    """Recursively find call_expression nodes and return short callee names."""
    calls = []
    for child in node.children:
        if child.type == "call_expression":
            callee_node = child.children[0] if child.children else None
            if callee_node:
                callee_short = _resolve_callee_name(callee_node)
                if callee_short and callee_short in known_short_names:
                    calls.append(callee_short)
        calls.extend(_collect_call_expressions_simple(child, known_short_names))
    return calls


def _resolve_callee_name(node) -> str:
    """Resolve a callee node to a short function name."""
    if node.type == "identifier":
        return node.text.decode()
    if node.type == "qualified_identifier":
        parts = []
        for c in node.children:
            if c.type in ("namespace_identifier", "identifier", "type_identifier"):
                parts.append(c.text.decode())
        return ".".join(parts)
    if node.type == "field_expression":
        field_node = node.child_by_field_name("field")
        if field_node:
            return field_node.text.decode()
    return ""


def save_callgraph_json(graph: Dict[str, List[str]], output_path: str):
    """Save the call graph as a JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)
    print(f"Tree-sitter call graph saved to: {output_path}")


def load_callgraph_json(json_path: str) -> Dict[str, List[str]]:
    """Load a call graph from a JSON file."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading call graph JSON from {json_path}: {e}")
        return {}
