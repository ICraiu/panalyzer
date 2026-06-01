from __future__ import annotations


def node_id(prefix: str, value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum():
            safe.append(char)
        else:
            safe.append("_")
    return f"{prefix}_{''.join(safe)}"


def display_name(name: str) -> str:
    stripped = name.lstrip("_")
    replacements = {
        "FunctionDef": "Function",
        "AsyncFunctionDef": "Async Function",
        "ClassDef": "Class",
        "ImportFrom": "Import From",
        "Import": "Import",
        "Call": "Call",
        "AnalyzerConfig": "Analyzer Config",
        "PythonFileAnalyzer": "Python File Analyzer",
        "DiscoveredSymbol": "Discovered Symbol",
        "DiscoveredCall": "Discovered Call",
    }

    if stripped.startswith("visit_"):
        stripped = stripped.removeprefix("visit_")
        return f"visit {humanize_identifier(stripped, replacements)}"

    return humanize_identifier(stripped, replacements)


def humanize_identifier(name: str, replacements: dict[str, str]) -> str:
    if name in replacements:
        return replacements[name]

    for source, target in replacements.items():
        name = name.replace(source, target)

    parts = [part for part in name.split("_") if part]
    if parts:
        return " ".join(humanize_token(part) for part in parts)
    return humanize_token(name)


def humanize_token(token: str) -> str:
    words: list[str] = []
    current = ""
    for char in token:
        if current and char.isupper() and not current[-1].isupper():
            words.append(current)
            current = char
        else:
            current += char
    if current:
        words.append(current)
    return " ".join(word.capitalize() for word in words if word)
