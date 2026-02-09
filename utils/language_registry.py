# utils/language_registry.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import os

# --- Tier 2 constants: binary file detection + text file size limit ---
BINARY_EXTENSIONS = frozenset({
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp',
    '.mp3', '.mp4', '.wav', '.avi', '.mov',
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
    '.exe', '.dll', '.so', '.dylib', '.bin', '.wasm',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.pyc', '.class', '.o', '.obj', '.a', '.lib',
    '.ttf', '.otf', '.woff', '.woff2',
    '.db', '.sqlite', '.sqlite3',
})
MAX_TEXT_FILE_SIZE = 512 * 1024  # 512 KB


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
        # --- Tier 1 expansion: 9 additional languages ---
        self.register(LanguageConfig(
            name="rust",
            extensions=[".rs"],
            code_fence_tag="rust",
            pmd_cpd_language="",
            tree_sitter_language="rust",
            grammar=TreeSitterGrammar(
                function_types=["function_item"],
                class_types=["struct_item", "impl_item"],
                class_body_type="declaration_list",
                function_body_type="block",
                call_types=["call_expression"],
                container_types=[],
                name_strategy="field_name",
                class_name_type="type_identifier",
            ),
        ))
        self.register(LanguageConfig(
            name="ruby",
            extensions=[".rb"],
            code_fence_tag="ruby",
            pmd_cpd_language="ruby",
            tree_sitter_language="ruby",
            grammar=TreeSitterGrammar(
                function_types=["method", "singleton_method"],
                class_types=["class", "module"],
                class_body_type="body_statement",
                function_body_type="body_statement",
                call_types=["call"],
                container_types=[],
                name_strategy="field_name",
                class_name_type="constant",
            ),
        ))
        self.register(LanguageConfig(
            name="php",
            extensions=[".php"],
            code_fence_tag="php",
            pmd_cpd_language="php",
            tree_sitter_language="php",
            grammar=TreeSitterGrammar(
                function_types=["function_definition", "method_declaration"],
                class_types=["class_declaration"],
                class_body_type="declaration_list",
                function_body_type="compound_statement",
                call_types=["call_expression"],
                container_types=["namespace_definition"],
                name_strategy="field_name",
                class_name_type="name",
            ),
        ))
        self.register(LanguageConfig(
            name="csharp",
            extensions=[".cs"],
            code_fence_tag="csharp",
            pmd_cpd_language="cs",
            tree_sitter_language="c_sharp",
            grammar=TreeSitterGrammar(
                function_types=["method_declaration", "constructor_declaration"],
                class_types=["class_declaration", "interface_declaration"],
                class_body_type="declaration_list",
                function_body_type="block",
                call_types=["invocation_expression"],
                container_types=["namespace_declaration"],
                name_strategy="field_name",
                class_name_type="identifier",
            ),
        ))
        self.register(LanguageConfig(
            name="kotlin",
            extensions=[".kt", ".kts"],
            code_fence_tag="kotlin",
            pmd_cpd_language="kotlin",
            tree_sitter_language="kotlin",
            grammar=TreeSitterGrammar(
                function_types=["function_declaration"],
                class_types=["class_declaration", "object_declaration"],
                class_body_type="class_body",
                function_body_type="function_body",
                call_types=["call_expression"],
                container_types=[],
                name_strategy="field_name",
                class_name_type="identifier",
            ),
        ))
        self.register(LanguageConfig(
            name="scala",
            extensions=[".scala"],
            code_fence_tag="scala",
            pmd_cpd_language="scala",
            tree_sitter_language="scala",
            grammar=TreeSitterGrammar(
                function_types=["function_definition"],
                class_types=["class_definition", "object_definition"],
                class_body_type="template_body",
                function_body_type="block",
                call_types=["call_expression"],
                container_types=[],
                name_strategy="field_name",
                class_name_type="identifier",
            ),
        ))
        self.register(LanguageConfig(
            name="lua",
            extensions=[".lua"],
            code_fence_tag="lua",
            pmd_cpd_language="lua",
            tree_sitter_language="lua",
            grammar=TreeSitterGrammar(
                function_types=["function_declaration", "function_definition_statement"],
                class_types=[],
                class_body_type="",
                function_body_type="block",
                call_types=["function_call"],
                container_types=[],
                name_strategy="field_name",
                class_name_type="",
            ),
        ))
        self.register(LanguageConfig(
            name="bash",
            extensions=[".sh", ".bash"],
            code_fence_tag="bash",
            pmd_cpd_language="",
            tree_sitter_language="bash",
            grammar=TreeSitterGrammar(
                function_types=["function_definition"],
                class_types=[],
                class_body_type="",
                function_body_type="compound_statement",
                call_types=["command"],
                container_types=[],
                name_strategy="field_name",
                class_name_type="",
            ),
        ))
        self.register(LanguageConfig(
            name="zig",
            extensions=[".zig"],
            code_fence_tag="zig",
            pmd_cpd_language="",
            tree_sitter_language="zig",
            grammar=TreeSitterGrammar(
                function_types=["function_declaration"],
                class_types=[],
                class_body_type="",
                function_body_type="block",
                call_types=["call_expression"],
                container_types=[],
                name_strategy="field_name",
                class_name_type="",
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
        """Return unique PMD/CPD language identifiers for all registered languages.
        Skips languages with no PMD support (empty pmd_cpd_language)."""
        seen = set()
        result = []
        for lang in self._languages.values():
            if lang.pmd_cpd_language and lang.pmd_cpd_language not in seen:
                seen.add(lang.pmd_cpd_language)
                result.append(lang.pmd_cpd_language)
        return result

    def get_tree_sitter_languages(self) -> List["LanguageConfig"]:
        """Return all language configs that have tree-sitter support."""
        return [lang for lang in self._languages.values()
                if lang.tree_sitter_language is not None]

    def is_binary_extension(self, file_path: str) -> bool:
        """Check if a file has a known binary extension."""
        _, ext = os.path.splitext(file_path)
        return ext.lower() in BINARY_EXTENSIONS

    def is_text_file_candidate(self, file_path: str) -> bool:
        """Check if a file could be a Tier 2 text file (not a registered language, not binary)."""
        if self.is_supported(file_path):
            return False  # Already a Tier 1 language
        return not self.is_binary_extension(file_path)


# Module-level convenience instance
registry = LanguageRegistry.get_instance()
