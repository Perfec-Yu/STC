# A Simple-Tool-Calling (STC) Contract for LLMs (experimental)

A tool calling contract designed for arguments with complex structures. Experimental and under development.

## Motivation
Handling nested structures is always a headache. Model developers have gradually shift from JSON-based tool calling to XML-style tool calling to avoid escaping of strings. However, it is still challenging to handle arguments that has nested structure:
- Some solutions dump object arguments to json -> nested arguments remain nested and escaped.
- Some solutions completely rollout the structure completely as a nested xml -> nested arguments remain nested, although not escaped.

The idea of this contract is to flatten the structure, thus allowing model to build the nested structure bottom up.

## Format

Simply put, when presenting a nested structure, keys are combined via dots. For example `a.b.c: 1` represents

```
{
    "a": {
        "b": {
            "c": 1
        }
    }
}
```

For arrays, use `$i` to indicate the i-th elements.

## Build (Experimental)
We use rust backend for fast parsing of recursive structures, and expose as a python-importable function. Build with `maturin`.
```
maturin build
pip install -e .
```

Still new to rust-python building and exploring the best ways. The current pipeline was mostly copying the structure from `openai-harmony`, siginificantly simplified due to the volume of this repo.

## Limitations

This format is still unideal for massive structures with patterns, e.g. `lst: list(range(1000))`. Another tool calling contract is under preparation to handle such cases.