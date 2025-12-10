use pyo3::prelude::*;
use serde_json::{Map, Number, Value};
use std::collections::HashMap;
use pyo3::{create_exception, exceptions::PyException, PyErr};
use pyo3::types::{PyBool, PyDict, PyFloat, PyList, PyInt, PyString};

create_exception!(stc_rust, STCParseError, PyException);

// Helper that builds a PyErr of type STCParseError
fn err<S: Into<String>>(s: S, ln: Option<usize>) -> PyErr {
    let m = s.into();
    let msg = if let Some(ln) = ln {
        format!("Line {ln}: {m}")
    } else {
        m
    };
    STCParseError::new_err(msg) // returns PyErr
}

#[derive(Debug, Clone)]
enum EmptyObject {
    EmptyList,
    EmptyDict,
}

#[derive(Debug, Clone)]
enum Node {
    Map(HashMap<String, Node>),
    Bool(bool),
    Int(i64),
    Float(f64),
    Str(String),
    Empty(EmptyObject),
}

impl Node {
    fn new_map() -> Self {
        Node::Map(HashMap::new())
    }
    fn as_map_mut(&mut self) -> Result<&mut HashMap<String, Node>, PyErr> {
        match self {
            Node::Map(m) => Ok(m),
            _ => Err(err("Internal: expected map node", None)),
        }
    }
}

fn value_to_pyobj(py: Python<'_>, v: &Value) -> PyResult<PyObject> {
    Ok(match v {
        Value::Null => py.None().into(), // Py<PyAny> == PyObject

        Value::Bool(b) => {
            // Bound<PyAny>
            let any = <pyo3::Bound<'_, PyBool> as Clone>::clone(&PyBool::new(py, *b)).into_any();
            // If you need Py<PyAny>, call .unbind():
            // let obj: Py<PyAny> = any.unbind();
            any.into()
        }

        Value::Number(num) => {
            if let Some(i) = num.as_i64() {
                PyInt::new(py, i).into_any().unbind()
            } else if let Some(u) = num.as_u64() {
                PyInt::new(py, u).into_any().unbind()
            } else if let Some(f) = num.as_f64() {
                PyFloat::new(py, f).into_any().unbind()
            } else {
                return Err(STCParseError::new_err("Invalid JSON number"));
            }
        }

        Value::String(s) => PyString::new(py, s).into_any().unbind(),

        Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                // value_to_pyobj -> PyObject, bind to this GIL to append
                list.append(value_to_pyobj(py, item)?.bind(py))?;
            }
            list.into_any().unbind()
        }

        Value::Object(obj) => {
            let dict = PyDict::new(py);
            for (k, val) in obj {
                dict.set_item(k, value_to_pyobj(py, val)?.bind(py))?;
            }
            dict.into_any().unbind()
        }
    })
}

fn is_identifier(piece: &str) -> bool {
    // A pragmatic approximation of Python's str.isidentifier():
    // ASCII [A-Za-z_][A-Za-z0-9_]*  (adjust if you need full Unicode idents)
    let mut chars = piece.chars();
    match chars.next() {
        Some(c) if c == '_' || c.is_ascii_alphabetic() => (),
        _ => return false,
    }
    chars.all(|c| c == '_' || c.is_ascii_alphanumeric())
}

fn parse_key(key: &str, ln: Option<usize>) -> Result<Vec<String>, PyErr> {
    let mut path = Vec::new();
    for piece in key.split('.') {
        if piece.is_empty() {
            return Err(err(format!("Invalid key: {key}. Key must be a valid identifier."), ln));
        }
        if piece.starts_with('$') {
            let idx = &piece[1..];
            if idx.is_empty() || !idx.chars().all(|c| c.is_ascii_digit()) {
                return Err(err(
                    format!("Invalid key: {key}. List index must be $numeric."),
                    ln,
                ));
            }
            path.push(piece.to_string());
        } else {
            if !is_identifier(piece) {
                return Err(err(
                    format!("Invalid key: {key}. Key must be a valid identifier."),
                    ln,
                ));
            }
            path.push(piece.to_string());
        }
    }
    Ok(path)
}

enum ParsedValue {
    Immediate(Node),
    StringStart { bt_count: usize },
}

fn parse_value(raw: &str, ln: Option<usize>) -> Result<ParsedValue, PyErr> {
    match raw {
        "`true`" => return Ok(ParsedValue::Immediate(Node::Bool(true))),
        "`false`" => return Ok(ParsedValue::Immediate(Node::Bool(false))),
        "[]" => return Ok(ParsedValue::Immediate(Node::Empty(EmptyObject::EmptyList))),
        "{}" => return Ok(ParsedValue::Immediate(Node::Empty(EmptyObject::EmptyDict))),
        _ => {}
    }

    // int?
    if let Ok(v) = raw.parse::<i64>() {
        return Ok(ParsedValue::Immediate(Node::Int(v)));
    }
    // float?
    if let Ok(v) = raw.parse::<f64>() {
        return Ok(ParsedValue::Immediate(Node::Float(v)));
    }

    // string block?
    if raw.starts_with("```") {
        let bt_count = raw.chars().take_while(|&c| c == '`').count();
        return Ok(ParsedValue::StringStart { bt_count });
    }

    Err(err(
        format!(
            "Invalid value: {raw}. Value must be:\n\
             - `true`, `false` for boolean\n\
             - `[]` for an empty list\n\
             - a number for integer or float\n\
             - a string block enclosed in backticks \
             (`, with the number of backticks larger than \
             the maximum consecutive number of backticks in the string)."
        ),
        ln,
    ))
}

fn fill_in_value(root: &mut Node, path: &[String], value: Node) -> Result<(), PyErr> {
    // Traverse or create maps along the way, then set the final key.
    let mut current = root;
    for (i, piece) in path.iter().enumerate().take(path.len().saturating_sub(1)) {
        // ensure current is a map
        if matches!(current, Node::Map(_)) == false {
            let joined = path[..=i].join(".");
            return Err(err(format!(
                "Key `{}` is set both a value and at least one list item / dict attribute.",
                joined
            ), None));
        }
        // descend / create
        let map = current.as_map_mut()?;
        current = map.entry(piece.clone()).or_insert_with(Node::new_map);
        if !matches!(current, Node::Map(_)) && i + 1 < path.len() - 1 {
            let joined = path[..=i].join(".");
            return Err(err(format!(
                "Key `{}` is set both a value and at least one list item / dict attribute.",
                joined
            ), None));
        }
    }
    // set the last piece
    let last = path.last().expect("nonempty path");
    let map = current.as_map_mut()?;
    if let Some(existing) = map.get(last) {
        match existing {
            Node::Map(_) => {
                return Err(err(format!(
                    "Key `{}` is set both a value directly and at least one list item / dict attribute.",
                    path.join(".")
                ), None));
            }
            _ => {
                return Err(err(format!(
                    "Key `{}` is set at least two values {:?} | {:?}.",
                    path.join("."), existing_short(existing), existing_short(&value)
                ), None));
            }
        }
    }
    map.insert(last.clone(), value);
    Ok(())
}

fn existing_short(n: &Node) -> String {
    match n {
        Node::Map(_) => "Map".into(),
        Node::Bool(b) => format!("Bool({b})"),
        Node::Int(i) => format!("Int({i})"),
        Node::Float(f) => format!("Float({f})"),
        Node::Str(s) => format!("Str({:?})", s),
        Node::Empty(EmptyObject::EmptyList) => "EmptyList".into(),
        Node::Empty(EmptyObject::EmptyDict) => "EmptyDict".into(),
    }
}

fn finalize_node(n: Node, prefix: &str) -> Result<Value, PyErr> {
    match n {
        Node::Bool(b) => Ok(Value::Bool(b)),
        Node::Int(i) => Ok(Value::Number(Number::from(i))),
        Node::Float(f) => {
            Number::from_f64(f)
                .map(Value::Number)
                .ok_or_else(|| err("Invalid float value (NaN/inf) not representable in JSON", None))
        }
        Node::Str(s) => Ok(Value::String(s)),
        Node::Empty(EmptyObject::EmptyList) => Ok(Value::Array(vec![])),
        Node::Empty(EmptyObject::EmptyDict) => Ok(Value::Object(Map::new())),
        Node::Map(m) => finalize_map(m, prefix),
    }
}

fn finalize_map(mut d: HashMap<String, Node>, prefix: &str) -> Result<Value, PyErr> {
    if d.is_empty() {
        return Ok(Value::Object(Map::new()));
    }
    let mut keys: Vec<String> = d.keys().cloned().collect();
    keys.sort();

    let here = if prefix.is_empty() { "<root>".to_string() } else { prefix.to_string() };
    let is_list = keys.first().map(|k| k.starts_with('$')).unwrap_or(false);

    if is_list {
        if keys.iter().any(|k| !k.starts_with('$')) {
            return Err(err(format!("{here} is set both as a list and a dict."), None));
        }
        let mut indices = Vec::with_capacity(keys.len());
        for k in &keys {
            let idx: usize = k[1..].parse().map_err(|_| err(format!("{here} has invalid list index `{k}`."), None))?;
            indices.push(idx);
        }
        if indices.iter().min() != Some(&0) || indices.iter().max() != Some(&(indices.len() - 1)) {
            return Err(err(format!("{here} is set as a list, but not all indices 0..{} are present.", indices.len()-1), None));
        }
        let mut arr = vec![Value::Null; indices.len()];
        for k in keys {
            let idx: usize = k[1..].parse().map_err(|_| err(format!("{here} has invalid list index `{k}`."), None))?;
            let child = d.remove(&k).ok_or_else(|| {
                err(
                    format!("Internal error: key `{k}` missing while finalizing list at {here}."),
                    None,
                )
            })?;
            let next_prefix = if prefix.is_empty() { k.clone() } else { format!("{prefix}.{k}") };
            arr[idx] = finalize_node(child, &next_prefix)?;
        }
        Ok(Value::Array(arr))
    } else {
        if keys.iter().any(|k| k.starts_with('$')) {
            return Err(err(format!("{here} is set both as a list and a dict."), None));
        }
        let mut obj = Map::new();
        for k in keys {
            let child = d.remove(&k).ok_or_else(|| {
                err(
                    format!("Internal error: key `{k}` missing while finalizing dict at {here}."),
                    None,
                )
            })?;
            let next_prefix = if prefix.is_empty() { k.clone() } else { format!("{prefix}.{k}") };
            obj.insert(k, finalize_node(child, &next_prefix)?);
        }
        Ok(Value::Object(obj))
    }
}

/// Parse STC from &str into serde_json::Value
pub fn parse_stc(input: &str) -> Result<Value, PyErr> {
    if input.trim() == "{}" {
        return Ok(Value::Object(Map::new()));
    }

    let mut root = Node::new_map();

    let mut in_string = false;
    let mut string_bt_count: usize = 0;
    let mut string_path: Vec<String> = Vec::new();
    let mut string_buf = String::new();

    for (idx, raw_line) in input.split('\n').enumerate() {
        let ln = idx + 1;

        if !in_string {
            if raw_line.trim().is_empty() {
                continue;
            }
            let Some(colon_idx) = raw_line.find(':') else {
                return Err(err(
                    format!("Line {ln} missing `:`. Line content:\n {raw_line}"),
                    None,
                ));
            };
            let (k, v) = raw_line.split_at(colon_idx);
            let key = k.trim();
            let value = v[1..].trim().to_string(); // skip ':'

            let key_path = parse_key(key, Some(ln))?;
            match parse_value(&value, Some(ln))? {
                ParsedValue::Immediate(n) => {
                    fill_in_value(&mut root, &key_path, n)?;
                }
                ParsedValue::StringStart { bt_count } => {
                    in_string = true;
                    string_bt_count = bt_count;
                    string_path = key_path;
                    string_buf.clear();
                    // The immediate newline after opening fence is trimmed by design:
                    // we *start collecting from the next physical line* (which we do below).
                }
            }
        } else {
            // inside a string block
            let fence: String = std::iter::repeat('`').take(string_bt_count).collect();
            if raw_line.trim_end() == fence {
                if string_buf.is_empty() {
                    return Err(err(
                        "Empty string block should be formatted as `key: ```\\n\\n```, not ```\\n```.",
                        Some(ln),
                    ));
                }
                // drop the final '\n'
                if string_buf.ends_with('\n') {
                    string_buf.pop();
                }
                let s = std::mem::take(&mut string_buf);
                fill_in_value(&mut root, &string_path, Node::Str(s))?;
                in_string = false;
                string_path.clear();
                string_bt_count = 0;
            } else {
                // accumulate with the line + '\n'
                string_buf.push_str(raw_line);
                string_buf.push('\n');
            }
        }
    }

    if in_string {
        return Err(err(
            format!("Unclosed string block starting at line {}.", input.lines().count()),
            None,
        ));
    }

    finalize_node(root, "")
}

#[pyfunction]
fn loads(py: Python<'_>, s: &str) -> PyResult<PyObject> {
    let val = parse_stc(s)?;
    value_to_pyobj(py, &val)
}

#[pymodule]
fn stc_rust(_py: Python<'_>, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(loads, m)?)?;
    Ok(())
}