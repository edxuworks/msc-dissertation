"""Quick install verification script."""
import importlib

pkgs = [
    ("fitz", "pymupdf"),
    ("docling", "docling"),
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("sklearn", "scikit-learn"),
    ("pydantic", "pydantic"),
    ("anthropic", "anthropic"),
    ("openai", "openai"),
    ("google.generativeai", "google-generativeai"),
    ("transformers", "transformers"),
    ("peft", "peft"),
    ("bitsandbytes", "bitsandbytes"),
    ("trl", "trl"),
    ("datasets", "datasets"),
    ("evaluate", "evaluate"),
    ("matplotlib", "matplotlib"),
    ("codecarbon", "codecarbon"),
    ("loguru", "loguru"),
    ("rich", "rich"),
    ("jsonschema", "jsonschema"),
]

ok, fail = [], []
for mod, pkg in pkgs:
    try:
        importlib.import_module(mod)
        ok.append(pkg)
    except ImportError:
        fail.append(pkg)

print(f"OK    ({len(ok)}): {', '.join(ok)}")
print(f"MISSING ({len(fail)}): {', '.join(fail) if fail else 'none'}")
