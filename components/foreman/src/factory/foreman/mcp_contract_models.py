"""Resolve same-brick Pydantic DTO declarations from Python AST source."""
from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelStatus:
    state: str
    extra_forbid: bool = False
    reference: str | None = None


def module_name(path: str) -> str | None:
    marker = "/src/factory/"
    if marker not in path or not path.endswith(".py"):
        return None
    name = path.split(marker, 1)[1][:-3].replace("/", ".")
    return name[:-9] if name.endswith(".__init__") else name


def _brick(path: str) -> str:
    parts = path.split("/")
    return parts[parts.index("components") + 1] if "components" in parts else parts[parts.index("bases") + 1]


def _relative_module(module: str, level: int, target: str | None) -> str:
    parent = module.split(".")[:-level] if level else []
    parts = target.split(".") if target else []
    if parts[:1] == ["factory"]:
        parts = parts[1:]
    return ".".join(parent + parts)


def _expr_ref(node: ast.expr, refs: dict[str, str], module: str) -> str | None:
    if isinstance(node, ast.Name):
        return refs.get(node.id, f"{module}.{node.id}")
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        base = refs.get(node.value.id)
        return f"{base}.{node.attr}" if base else None
    return None


def _base_target(node: ast.expr, refs: dict[str, str], module: str) -> str | None:
    """Resolve a class base, including generic bases such as RootModel[T]."""
    return _expr_ref(node.value if isinstance(node, ast.Subscript) else node, refs, module)


def _forbid(node: ast.ClassDef) -> bool:
    for item in node.body:
        if not isinstance(item, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "model_config" for target in item.targets
        ) or not isinstance(item.value, ast.Call):
            continue
        if any(keyword.arg == "extra" and isinstance(keyword.value, ast.Constant)
               and keyword.value.value == "forbid" for keyword in item.value.keywords):
            return True
    return False


class ModelResolver:
    """Resolve Pydantic classes only within a tool's owning brick."""

    def __init__(self, sources: dict[str, str]) -> None:
        self._classes: dict[str, tuple[ast.ClassDef, str]] = {}
        self._refs: dict[str, dict[str, str]] = {}
        for path, source in sources.items():
            module = module_name(path)
            if module is None:
                continue
            tree = ast.parse(source, filename=path)
            refs: dict[str, str] = {}
            for node in tree.body:
                if isinstance(node, ast.ImportFrom):
                    imported = _relative_module(module, node.level, node.module)
                    for item in node.names:
                        alias = item.asname or item.name
                        refs[alias] = f"{imported}.{item.name}" if item.name != "*" else imported
                elif isinstance(node, ast.Import):
                    for item in node.names:
                        target = item.name.removeprefix("factory.")
                        refs[item.asname or item.name.split(".")[0]] = target
                elif isinstance(node, ast.ClassDef):
                    self._classes[f"{module}.{node.name}"] = (node, _brick(path))
            self._refs[module] = refs

    def inspect(self, module: str, value: ast.expr | None, brick: str) -> ModelStatus:
        ref = _expr_ref(value, self._refs.get(module, {}), module) if value else None
        if ref is None or ref not in self._classes or self._classes[ref][1] != brick:
            return ModelStatus("unresolved", reference=ref)
        if not self._is_model(ref, set()):
            return ModelStatus("non_pydantic", reference=ref)
        return ModelStatus("valid", self._forbid(ref, set()), ref)

    def _forbid(self, ref: str, seen: set[str]) -> bool:
        if ref in seen:
            return False
        seen.add(ref)
        node, _ = self._classes[ref]
        if _forbid(node):
            return True
        module = ref.rsplit(".", 1)[0]
        for base in node.bases:
            target = _base_target(base, self._refs.get(module, {}), module)
            if target in {"pydantic.RootModel", "pydantic.root_model.RootModel"}:
                return True
            if target in self._classes and self._forbid(target, seen):
                return True
        return False

    def _is_model(self, ref: str, seen: set[str]) -> bool:
        if ref in seen:
            return False
        seen.add(ref)
        node, _ = self._classes[ref]
        module = ref.rsplit(".", 1)[0]
        for base in node.bases:
            target = _base_target(base, self._refs.get(module, {}), module)
            if target in {"pydantic.BaseModel", "pydantic.main.BaseModel",
                          "pydantic.RootModel", "pydantic.root_model.RootModel"}:
                return True
            if target in self._classes and self._is_model(target, seen):
                return True
        return False
