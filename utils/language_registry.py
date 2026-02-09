# utils/language_registry.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import os


@dataclass
class TreeSitterGrammar:
    """Data-driven description of a language's tree-sitter AST node types."""
    function_types: List[str]       # e.g. ["method_declaration", "constructor_declaration"]
    class_types: List[str]          # e.g. ["class_declaration", "interface_declaration"]
    class_body_type: str            # e.g. "class_body", "field_declaration_list"
    function_body_type: str         # e.g. "block", "compound_statement", "statement_block"
    call_types: List[str]           # e.g. ["method_invocation"], ["call_expression"]
    container_types: List[str]      # e.g. ["namespace_definition"] for C++
    name_strategy: str              # "field_name" or "declarator"
    class_name_type: str            # e.g. "type_identifier", "identifier"


@dataclass
class LanguageConfig:
    """Configuration for a supported programming language."""
    name: str                       # e.g. "python", "c", "cpp"
    extensions: List[str]           # e.g. [".py"], [".c", ".h"]
    code_fence_tag: str             # e.g. "python", "c", "cpp"
    pmd_cpd_language: str           # PMD/CPD language identifier
    has_pyan_support: bool = False  # Only Python has pyan support
    tree_sitter_language: Optional[str] = None  # e.g. "c", "cpp"
    grammar: Optional[TreeSitterGrammar] = None


class LanguageRegistry:
    """Central registry for all language-specific logic."""

    _instance = None

    def __init__(self):
        self._languages: Dict[str, LanguageConfig] = {}
        self._ext_map: Dict[str, LanguageConfig] = {}
        self._register_builtin_languages()

    @classmethod
    def get_instance(cls) -> "LanguageRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _register_builtin_languages(self):
        self.register(LanguageConfig(
            name="python",
            extensions=[".py"],
            code_fence_tag="python",
            pmd_cpd_language="python",
            has_pyan_support=True,
            tree_sitter_language=None,  # Python uses ast module, not tree-sitter
        ))
        self.register(LanguageConfig(
            name="c",
            extensions=[".c", ".h"],
            code_fence_tag="c",
            pmd_cpd_language="c",
            has_pyan_support=False,
            tree_sitter_language="c",
            grammar=TreeSitterGrammar(
                function_types=["function_definition"],
                class_types=["struct_specifier"],
                class_body_type="field_declaration_list",
                function_body_type="compound_statement",
                call_types=["call_expression"],
                container_types=[],
                name_strategy="declarator",
                class_name_type="type_identifier",
            ),
        ))
        self.register(LanguageConfig(
            name="cpp",
            extensions=[".cpp", ".cc", ".cxx", ".hpp", ".hxx"],
            code_fence_tag="cpp",
            pmd_cpd_language="cpp",
            has_pyan_support=False,
            tree_sitter_language="cpp",
            grammar=TreeSitterGrammar(
                function_types=["function_definition"],
                class_types=["class_specifier", "struct_specifier"],
                class_body_type="field_declaration_list",
                function_body_type="compound_statement",
                call_types=["call_expression"],
                container_types=["namespace_definition"],
                name_strategy="declarator",
                class_name_type="type_identifier",
            ),
        ))
        self.register(LanguageConfig(
            name="java",
            extensions=[".java"],
            code_fence_tag="java",
            pmd_cpd_language="java",
            tree_sitter_language="java",
            grammar=TreeSitterGrammar(
                function_types=["method_declaration", "constructor_declaration"],
                class_types=["class_declaration", "interface_declaration", "enum_declaration"],
                class_body_type="class_body",
                function_body_type="block",
                call_types=["method_invocation"],
                container_types=[],
                name_strategy="field_name",
                class_name_type="identifier",
            ),
        ))
        self.register(LanguageConfig(
            name="go",
            extensions=[".go"],
            code_fence_tag="go",
            pmd_cpd_language="go",
            tree_sitter_language="go",
            grammar=TreeSitterGrammar(
                function_types=["function_declaration", "method_declaration"],
                class_types=[],
                class_body_type="",
                function_body_type="block",
                call_types=["call_expression"],
                container_types=[],
                name_strategy="field_name",
                class_name_type="",
            ),
        ))
        self.register(LanguageConfig(
            name="javascript",
            extensions=[".js", ".jsx", ".mjs"],
            code_fence_tag="javascript",
            pmd_cpd_language="ecmascript",
            tree_sitter_language="javascript",
            grammar=TreeSitterGrammar(
                function_types=["function_declaration", "method_definition", "arrow_function"],
                class_types=["class_declaration"],
                class_body_type="class_body",
                function_body_type="statement_block",
                call_types=["call_expression"],
                container_types=[],
                name_strategy="field_name",
                class_name_type="identifier",
            ),
        ))
        self.register(LanguageConfig(
            name="typescript",
            extensions=[".ts", ".tsx"],
            code_fence_tag="typescript",
            pmd_cpd_language="typescript",
            tree_sitter_language="typescript",
            grammar=TreeSitterGrammar(
                function_types=["function_declaration", "method_definition", "arrow_function"],
                class_types=["class_declaration"],
                class_body_type="class_body",
                function_body_type="statement_block",
                call_types=["call_expression"],
                container_types=[],
                name_strategy="field_name",
                class_name_type="type_identifier",
            ),
        ))

    def register(self, config: LanguageConfig):
        self._languages[config.name] = config
        for ext in config.extensions:
            self._ext_map[ext] = config

    def detect_language(self, file_path: str) -> Optional[LanguageConfig]:
        """Detect language from file extension. Returns None if unsupported."""
        _, ext = os.path.splitext(file_path)
        return self._ext_map.get(ext.lower())

    def is_supported(self, file_path: str) -> bool:
        """Check if a file is in a supported language."""
        return self.detect_language(file_path) is not None

    def get_all_extensions(self) -> Set[str]:
        """Return all registered file extensions."""
        return set(self._ext_map.keys())

    def get_all_languages(self) -> List[LanguageConfig]:
        """Return all registered language configs."""
        return list(self._languages.values())

    def get_language(self, name: str) -> Optional[LanguageConfig]:
        """Get a language config by name."""
        return self._languages.get(name)

    def strip_extension(self, file_path: str) -> str:
        """Strip the language-specific extension from a file path."""
        root, ext = os.path.splitext(file_path)
        if ext.lower() in self._ext_map:
            return root
        return file_path

    def get_code_fence_tag(self, file_path: str) -> str:
        """Get the markdown code fence language tag for a file."""
        lang = self.detect_language(file_path)
        if lang:
            return lang.code_fence_tag
        return ""

    def get_pmd_languages(self) -> List[str]:
        """Return unique PMD/CPD language identifiers for all registered languages."""
        seen = set()
        result = []
        for lang in self._languages.values():
            if lang.pmd_cpd_language not in seen:
                seen.add(lang.pmd_cpd_language)
                result.append(lang.pmd_cpd_language)
        return result


# Module-level convenience instance
registry = LanguageRegistry.get_instance()
