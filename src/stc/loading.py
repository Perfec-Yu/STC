from .exceptions import STCParseError
from enum import Enum
from typing import Any, Literal, TextIO

try:
    from stc_rust import loads as rust_loads
except ImportError:
    rust_loads = None

class EmptyObject(Enum):
    EMPTY_LIST = []
    EMPTY_DICT = {}


def raise_parse_error(message: str, ln: int | None = None) -> STCParseError:
    """
    Raises a STCParseError with a formatted message.
    
    Args:
        message (str): The error message to display.
        ln (int | None): The line number where the error occurred, if applicable.
        
    Returns:
        STCParseError: The raised exception.
    """
    if ln is not None:
        message = f"Line {ln}: {message}"
    raise STCParseError(message)


def parse_key(key: str, ln: int | None = None) -> None:
    pieces = key.split(".")
    path = []
    for piece in pieces:
        if not piece.isidentifier():
            raise_parse_error(f"Invalid key: {key}. Key must be a valid identifier.", ln)
        if piece[0] == '$':
            if not piece[1:].isnumeric():
                raise_parse_error(f"Invalid key: {key}. List index must be $numeric.", ln)
            if int(piece[1:]) < 0:
                raise_parse_error(f"Negative list index in key: {key}.", ln)
        path.append(piece)
    return path


def parse_value(value: str, ln: int | None = None) -> tuple[Any, bool]:
    """
    Parse the value from a line.
    If the value is not a string block start, it returns the value and is_string as False.
    If the value is a string block start, it returns the number of backticks and is_string as True.
    """
    if value == "`true`":
        return True, False
    if value == "`false`":
        return False, False
    if value == "[]":
        return EmptyObject.EMPTY_LIST, False
    if value == "{}":
        return EmptyObject.EMPTY_DICT, False
    try:
        return int(value), False
    except Exception:
        pass
    try:
        return float(value), False
    except Exception:
        pass
    # string
    if not value.startswith("```"):
        raise_parse_error(
            (
                f"Invalid value: {value}. Value must be:\n"
                "- `true`, `false` for boolean\n"
                "- `[]` for an empty list\n"
                "- a number for integer or float\n"
                "- a string block enclosed in backticks "
                "(`, with the number of backticks larger than "
                "the maximum consecutive number of backticks in the string)."
            )
        , ln)
    bt_count = len(value) - len(value.lstrip("`"))
    return bt_count, True
    

def fill_in_value(path: list[str], value: Any, parsed: dict) -> None:
    """
    Fills in the value in the parsed dictionary at the specified path.
    
    Args:
        path (list[str]): The path to the key in the dictionary.
        value (Any): The value to set at the specified path.
        parsed (dict): The dictionary to fill in.
    """
    
    current = parsed
    for i, piece in enumerate(path[:-1]):
        if piece not in current:
            current[piece] = {}
        elif not isinstance(current[piece], dict):
            raise_parse_error(f"Key `{'.'.join(path[:i + 1])}` is set both a value and at least one list item / dict attribute.", None)
        current = current[piece]
    
    last_piece = path[-1]

    if last_piece in current:
        if isinstance(current[last_piece], dict):
            raise_parse_error(f"Key `{'.'.join(path)}` is set both a value directly and at least one list item / dict attribute.", None)
        else:
            raise_parse_error(f"Key `{'.'.join(path)}` is set at least two values {current[piece]} | {value}.", None)
    else:
        current[last_piece] = value


def finalize_dict(d: dict, prefix: str) -> dict:
    """
    Finalizes the parsed dictionary by converting EmptyObject values to their actual types.
    
    Args:
        d (dict): The parsed dictionary.
        
    Returns:
        dict: The finalized dictionary with EmptyObject values replaced.
    """
    if len(d) == 0:
        return d
    keys = list(d.keys())
    if keys[0][0] == '$':
        if any(key[0] != '$' for key in keys):
            raise_parse_error(f"{prefix} is set both as a list and a dict.", None)
        all_indices = [int(key[1:]) for key in keys]
        if min(all_indices) != 0 or max(all_indices) != len(all_indices) - 1:
            raise_parse_error(f"{prefix} is set as a list, but not all indices are present.", None)
        list_data = [None for _ in range(len(all_indices))]
        for key in keys:
            index = int(key[1:])
            if isinstance(d[key], dict):
                list_data[index] = finalize_dict(d[key], f"{prefix}.{key}" if prefix else key)
            elif isinstance(d[key], EmptyObject):
                list_data[index] = d[key].value
            else:
                list_data[index] = d[key]
        return list_data
    else:
        if any(key[0] == '$' for key in keys):
            raise_parse_error(f"{prefix} is set both as a list and a dict.", None)
        for key, value in d.items():
            if isinstance(value, dict):
                d[key] = finalize_dict(value, f"{prefix}.{key}" if prefix else key)
            elif isinstance(value, EmptyObject):
                d[key] = value.value
    return d


def loads(stc_str: str, impl: Literal['rust', 'python'] = 'rust') -> dict:
    """
    Parses a string of STC and returns it as a dictionary.
    
    Args:
        stc_str (str): A string of STC configs.
        
    Returns:
        dict: The parsed data as a dictionary.
        
    Raises:
        STCParseError: If the input string is not valid.
    """
    if impl == 'rust':
        if rust_loads is not None:
            return rust_loads(stc_str)
        else:
            raise NotImplementedError("Rust implementation is not available.")
    if stc_str.strip() == "{}":
        return {}
    lines = stc_str.split("\n")
    in_a_string = False
    string_value = ""
    bt_count = -1
    string_key_path = None
    parsed = {}
    for line_num, line in enumerate(lines):
        if not in_a_string:
            if not line.strip():
                continue
            if ":" not in line:
                raise STCParseError(f"Line {line_num + 1} missing `:`. Line content:\n {line}")
            key, value = line.split(":", 1)
            key = key.strip()
            parsed_key_path = parse_key(key, line_num + 1)
            value = value.strip()
            parsed_value, is_string = parse_value(value, line_num + 1)
            if is_string:
                in_a_string = True
                string_value = ""
                string_key_path = parsed_key_path
                bt_count = parsed_value
            else:
                fill_in_value(parsed_key_path, parsed_value, parsed)
        else:
            if line.rstrip() == "`" * bt_count:
                if len(string_value) == 0:
                    raise STCParseError(f"Empty string block should be formated as `key: ```\\n\\n```, not ```\\n```.", line_num + 1)
                string_value = string_value[:-1]
                in_a_string = False
                fill_in_value(string_key_path, string_value, parsed)
                string_key_path = None
                string_value = ""
                bt_count = -1
            else:
                string_value += line + "\n"
    if in_a_string:
        raise STCParseError(f"Unclosed string block starting at line {line_num + 1}.")
    return finalize_dict(parsed, "")


def load(fp: TextIO) -> Any:
    """
    Parse a structure from a file-like object containing your DSL.

    Args:
        fp: Any text-mode file-like object (must support `.read()` returning str).

    Returns:
        The parsed Python object.

    Raises:
        Whatever exceptions `loads` may raise if the input is invalid.
    """
    return loads(fp.read())