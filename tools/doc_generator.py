#!/usr/bin/env python3
"""
Documentation Generator - Automatische API-Dokumentation für Kran-Tools.

Dieses Tool bietet:
- Docstring-Extraktion
- Markdown-Dokumentation
- HTML-Dokumentation (Sphinx-kompatibel)
- Module-Übersicht
- API-Referenz
"""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]


class DocGenerator:
    """
    Generator für automatische Dokumentation.
    
    Verwendung:
        generator = DocGenerator()
        generator.generate_module_docs("scripts")
        generator.save_markdown("docs/api.md")
    """

    def __init__(self):
        self.modules: Dict[str, Dict[str, Any]] = {}
        self.base_dir = BASE_DIR

    def analyze_module(self, module_path: Path) -> Dict[str, Any]:
        """
        Analysiert ein Python-Modul und extrahiert Dokumentation.
        
        Args:
            module_path: Pfad zum Python-Modul
            
        Returns:
            Dict mit Modul-Informationen
        """
        module_info = {
            "name": module_path.stem,
            "path": str(module_path.relative_to(self.base_dir)),
            "docstring": None,
            "functions": [],
            "classes": [],
        }

        try:
            with open(module_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            # Modul-Docstring
            module_info["docstring"] = ast.get_docstring(tree)

            # Funktionen
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.name.startswith("_"):  # Keine privaten Funktionen
                        func_info = {
                            "name": node.name,
                            "docstring": ast.get_docstring(node),
                            "args": [arg.arg for arg in node.args.args],
                        }
                        module_info["functions"].append(func_info)

                elif isinstance(node, ast.ClassDef):
                    if not node.name.startswith("_"):  # Keine privaten Klassen
                        class_info = {
                            "name": node.name,
                            "docstring": ast.get_docstring(node),
                            "methods": [],
                        }

                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                if not item.name.startswith("_") or item.name == "__init__":
                                    method_info = {
                                        "name": item.name,
                                        "docstring": ast.get_docstring(item),
                                        "args": [arg.arg for arg in item.args.args][1:],  # Skip 'self'
                                    }
                                    class_info["methods"].append(method_info)

                        module_info["classes"].append(class_info)

        except Exception as e:
            print(f"Fehler beim Analysieren von {module_path}: {e}")

        return module_info

    def generate_module_docs(self, directory: str):
        """
        Generiert Dokumentation für alle Module in einem Verzeichnis.
        
        Args:
            directory: Verzeichnis mit Python-Modulen
        """
        module_dir = self.base_dir / directory

        if not module_dir.exists():
            print(f"Verzeichnis nicht gefunden: {module_dir}")
            return

        for py_file in module_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_info = self.analyze_module(py_file)
            self.modules[module_info["name"]] = module_info

        print(f"Dokumentation für {len(self.modules)} Module generiert")

    def generate_markdown(self) -> str:
        """
        Generiert Markdown-Dokumentation.
        
        Returns:
            Markdown-String
        """
        lines = ["# API-Dokumentation", "", "Automatisch generierte Dokumentation für Kran-Tools.", ""]

        # Inhaltsverzeichnis
        lines.append("## Inhaltsverzeichnis")
        lines.append("")
        for module_name in sorted(self.modules.keys()):
            lines.append(f"- [{module_name}](#{module_name})")
        lines.append("")

        # Module
        for module_name, module_info in sorted(self.modules.items()):
            lines.append(f"## {module_name}")
            lines.append("")

            if module_info["docstring"]:
                lines.append(module_info["docstring"])
                lines.append("")

            # Funktionen
            if module_info["functions"]:
                lines.append("### Funktionen")
                lines.append("")

                for func in module_info["functions"]:
                    args_str = ", ".join(func["args"])
                    lines.append(f"#### `{func['name']}({args_str})`")
                    lines.append("")

                    if func["docstring"]:
                        lines.append(func["docstring"])
                    else:
                        lines.append("*Keine Dokumentation verfügbar*")
                    lines.append("")

            # Klassen
            if module_info["classes"]:
                lines.append("### Klassen")
                lines.append("")

                for cls in module_info["classes"]:
                    lines.append(f"#### `{cls['name']}`")
                    lines.append("")

                    if cls["docstring"]:
                        lines.append(cls["docstring"])
                        lines.append("")

                    if cls["methods"]:
                        lines.append("**Methoden:**")
                        lines.append("")

                        for method in cls["methods"]:
                            args_str = ", ".join(method["args"])
                            lines.append(f"- `{method['name']}({args_str})`")

                            if method["docstring"]:
                                # Erste Zeile des Docstrings
                                first_line = method["docstring"].split("\n")[0]
                                lines.append(f"  - {first_line}")

                        lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def save_markdown(self, output_path: Path):
        """
        Speichert Markdown-Dokumentation.
        
        Args:
            output_path: Ausgabepfad
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        markdown = self.generate_markdown()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        print(f"Dokumentation gespeichert: {output_path}")

    def generate_module_overview(self) -> str:
        """
        Generiert eine Modul-Übersicht.
        
        Returns:
            Übersicht als String
        """
        lines = ["# Modul-Übersicht", "", ""]

        lines.append(f"{'Modul':<30} {'Funktionen':<15} {'Klassen':<15}")
        lines.append("-" * 60)

        for module_name, module_info in sorted(self.modules.items()):
            func_count = len(module_info["functions"])
            class_count = len(module_info["classes"])
            lines.append(f"{module_name:<30} {func_count:<15} {class_count:<15}")

        return "\n".join(lines)


def main():
    """Hauptfunktion für Dokumentations-Generator."""
    import argparse

    parser = argparse.ArgumentParser(description="Dokumentations-Generator für Kran-Tools")
    parser.add_argument("directory", help="Verzeichnis mit Python-Modulen")
    parser.add_argument("-o", "--output", default="docs/api.md", help="Ausgabe-Pfad")
    parser.add_argument("--overview", action="store_true", help="Nur Übersicht anzeigen")

    args = parser.parse_args()

    generator = DocGenerator()
    generator.generate_module_docs(args.directory)

    if args.overview:
        print(generator.generate_module_overview())
    else:
        output_path = Path(args.output)
        generator.save_markdown(output_path)


if __name__ == "__main__":
    main()
