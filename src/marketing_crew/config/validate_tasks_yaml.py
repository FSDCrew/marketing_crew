"""
This script validates the structure and integrity of the tasks.yaml file used
by the campAIgn engine. The validator ensures that:

1. The YAML file is syntactically valid and contains no duplicate keys.
    - A custom YAML loader (UniqueKeyLoader) is used to detect duplicate keys,
        which can silently overwrite values in normal YAML parsing.

2. The top-level structure contains the required sections:
    - `state.fields`: a registry of all flow state fields
    - `tasks`: a registry of all task definitions

3. Each entry in `state.fields` meets the required schema:
    - Field name must be a non-empty string.
    - Each field must define:
        - `type`: a non-empty string representing the field's data type
        - `field_kind`: one of the allowed categories (e.g., "context", "data")
    - This ensures the platform can correctly determine which fields are
        campaign context inputs and which are dynamic workflow data fields.

4. Each task definition in `tasks` is valid:
    - Every task must define a `key` matching the task name.
    - Every task must define an `agent` field referencing a valid agent.
    - Tasks may define `reads` and `writes` lists, each containing mappings:
        - `field`: the name of a state field referenced by the task
        - Optional `type`: if present, must match the field's declared type

5. All field references used by tasks are validated:
    - Any field in `reads` or `writes` must exist in `state.fields`.
    - If a task specifies a write-time type override, it must match the field's
        type defined under `state.fields`.
    - This ensures that all task I/O operations are consistent with the global
        field registry.

6. All agent assignments are validated:
    - Each task must have an `agent` field.
    - The agent referenced must exist in agents.yaml (located in the same directory
        as tasks.yaml).
    - This ensures that all tasks have valid agent assignments before execution.

This validation step prevents misconfigured workflows, mismatched types,
undefined fields, and accidental YAML mistakes before the runtime engine
attempts to build dynamic FlowState or execute task crews.
"""


import os
import sys
from typing import Any, Dict, Set

import yaml


# ---------- YAML loader that rejects duplicate keys ----------

class UniqueKeyLoader(yaml.SafeLoader):
    pass


def construct_mapping(loader: UniqueKeyLoader, node, deep=False):
    """Override mapping construction to error on duplicate keys."""
    if not isinstance(node, yaml.MappingNode):
        raise yaml.constructor.ConstructorError(
            None, None,
            f"Expected a mapping node, but found {node.id}",
            node.start_mark,
        )

    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, (str, int, float, bool)):
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark,
                "found unacceptable key (%s)" % type(key),
                key_node.start_mark,
            )
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark,
                f"found duplicate key: {key!r}",
                key_node.start_mark,
            )
        value = loader.construct_object(value_node, deep=deep)
        mapping[key] = value
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_mapping,
)


# ---------- Validation helpers ----------

class ValidationError(Exception):
    pass


def load_yaml(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.load(f, Loader=UniqueKeyLoader)
    except yaml.YAMLError as e:
        raise ValidationError(f"YAML parsing error: {e}") from e
    except FileNotFoundError:
        raise ValidationError(f"File not found: {path}")
    if not isinstance(data, dict):
        raise ValidationError("Top-level YAML must be a mapping (dict).")
    return data


def ensure_dict(obj: Any, path: str) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValidationError(f"{path} must be a mapping (dict).")
    return obj


def ensure_list(obj: Any, path: str) -> Any:
    if not isinstance(obj, list):
        raise ValidationError(f"{path} must be a list.")
    return obj


# ---------- Core checks ----------

ALLOWED_FIELD_KINDS = {"context", "data"}


def validate_state_fields(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if "state" not in data:
        raise ValidationError("Missing top-level key: 'state'.")
    state = ensure_dict(data["state"], "state")

    if "fields" not in state:
        raise ValidationError("Missing key: 'state.fields'.")
    fields = ensure_dict(state["fields"], "state.fields")

    for field_name, field_def in fields.items():
        if not isinstance(field_name, str) or not field_name.strip():
            raise ValidationError(f"Field name must be a non-empty string, got: {field_name!r}")
        field_def = ensure_dict(field_def, f"state.fields.{field_name}")

        # type is required
        if "type" not in field_def:
            raise ValidationError(f"Field 'state.fields.{field_name}' is missing required key 'type'.")
        if not isinstance(field_def["type"], str) or not field_def["type"].strip():
            raise ValidationError(f"'type' for field 'state.fields.{field_name}' must be a non-empty string.")

        # field_kind is required
        if "field_kind" not in field_def:
            raise ValidationError(f"Field 'state.fields.{field_name}' is missing required key 'field_kind'.")

        kind = field_def["field_kind"]
        if not isinstance(kind, str) or not kind.strip():
            raise ValidationError(f"'field_kind' for field 'state.fields.{field_name}' must be a non-empty string.")

        if kind not in ALLOWED_FIELD_KINDS:
            raise ValidationError(
                f"Invalid field_kind={kind!r} for field 'state.fields.{field_name}'. "
                f"Allowed values: {sorted(ALLOWED_FIELD_KINDS)}"
            )

    return fields  # mapping: field_name -> field_def


def validate_tasks_block(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if "tasks" not in data:
        raise ValidationError("Missing top-level key: 'tasks'.")
    tasks = ensure_dict(data["tasks"], "tasks")

    for task_name, task_def in tasks.items():
        if not isinstance(task_name, str) or not task_name.strip():
            raise ValidationError(f"Task key must be a non-empty string, got: {task_name!r}")
        task_def = ensure_dict(task_def, f"tasks.{task_name}")

        # Each task must have a 'key' field
        if "key" not in task_def:
            raise ValidationError(f"Task 'tasks.{task_name}' is missing required key 'key'.")
        key_value = task_def["key"]
        if not isinstance(key_value, str) or not key_value.strip():
            raise ValidationError(f"'key' for task 'tasks.{task_name}' must be a non-empty string.")

        # Optionally enforce key == task_name
        if key_value != task_name:
            raise ValidationError(
                f"'key' for task 'tasks.{task_name}' must match task name; got key={key_value!r}."
            )

    return tasks  # mapping: task_name -> task_def


def collect_known_fields(fields: Dict[str, Dict[str, Any]]) -> Set[str]:
    return set(fields.keys())


def validate_task_io(tasks: Dict[str, Dict[str, Any]], fields: Dict[str, Dict[str, Any]]) -> None:
    known_fields = collect_known_fields(fields)

    for task_name, task_def in tasks.items():
        base_path = f"tasks.{task_name}"

        # --- validate reads ---
        if "reads" in task_def:
            reads = ensure_list(task_def["reads"], f"{base_path}.reads")
            for i, entry in enumerate(reads):
                entry_path = f"{base_path}.reads[{i}]"
                entry = ensure_dict(entry, entry_path)
                if "field" not in entry:
                    raise ValidationError(f"{entry_path} is missing required key 'field'.")
                field_name = entry["field"]
                if not isinstance(field_name, str) or not field_name.strip():
                    raise ValidationError(f"'field' in {entry_path} must be a non-empty string.")
                if field_name not in known_fields:
                    raise ValidationError(
                        f"{entry_path} references unknown field '{field_name}'. "
                        "Field must exist in state.fields."
                    )

        # --- validate writes ---
        if "writes" in task_def:
            writes = ensure_list(task_def["writes"], f"{base_path}.writes")
            for i, entry in enumerate(writes):
                entry_path = f"{base_path}.writes[{i}]"
                entry = ensure_dict(entry, entry_path)
                if "field" not in entry:
                    raise ValidationError(f"{entry_path} is missing required key 'field'.")
                field_name = entry["field"]
                if not isinstance(field_name, str) or not field_name.strip():
                    raise ValidationError(f"'field' in {entry_path} must be a non-empty string.")
                if field_name not in known_fields:
                    raise ValidationError(
                        f"{entry_path} references unknown field '{field_name}'. "
                        "Field must exist in state.fields."
                    )

                # If a type is specified in writes, validate it matches declared field type
                if "type" in entry and entry["type"] is not None:
                    write_type = entry["type"]
                    if not isinstance(write_type, str) or not write_type.strip():
                        raise ValidationError(f"'type' in {entry_path} must be a non-empty string if provided.")
                    declared_type = fields[field_name].get("type")
                    if write_type != declared_type:
                        raise ValidationError(
                            f"Type mismatch in {entry_path}: write type={write_type!r} "
                            f"but state.fields.{field_name}.type={declared_type!r}."
                        )


def load_agents_yaml(tasks_yaml_path: str) -> Dict[str, Dict[str, Any]]:
    """Load agents.yaml from the same directory as tasks.yaml."""
    tasks_dir = os.path.dirname(os.path.abspath(tasks_yaml_path))
    agents_path = os.path.join(tasks_dir, "agents.yaml")
    
    try:
        agents_data = load_yaml(agents_path)
    except ValidationError as e:
        raise ValidationError(f"Failed to load agents.yaml: {e}") from e
    
    return agents_data


def extract_agent_keys(agents_data: Dict[str, Dict[str, Any]]) -> Set[str]:
    """Extract valid agent keys from agents.yaml."""
    agent_keys = set()
    
    for agent_name, agent_def in agents_data.items():
        if not isinstance(agent_name, str) or not agent_name.strip():
            raise ValidationError(f"Agent name must be a non-empty string, got: {agent_name!r}")
        
        agent_def = ensure_dict(agent_def, f"agents.{agent_name}")
        
        # Check if agent has a 'key' field
        if "key" in agent_def:
            key_value = agent_def["key"]
            if not isinstance(key_value, str) or not key_value.strip():
                raise ValidationError(f"'key' for agent '{agent_name}' must be a non-empty string.")
            # Use the key value if it exists, otherwise use the agent name
            agent_keys.add(key_value)
        else:
            # If no key field, use the agent name itself
            agent_keys.add(agent_name)
    
    return agent_keys


def validate_task_agents(tasks: Dict[str, Dict[str, Any]], agents_data: Dict[str, Dict[str, Any]]) -> None:
    """Validate that each task has a valid agent assigned."""
    valid_agent_keys = extract_agent_keys(agents_data)
    
    for task_name, task_def in tasks.items():
        base_path = f"tasks.{task_name}"
        
        # Each task must have an 'agent' field
        if "agent" not in task_def:
            raise ValidationError(f"Task 'tasks.{task_name}' is missing required key 'agent'.")
        
        agent_name = task_def["agent"]
        if not isinstance(agent_name, str) or not agent_name.strip():
            raise ValidationError(f"'agent' for task 'tasks.{task_name}' must be a non-empty string.")
        
        # The agent must exist in agents.yaml
        if agent_name not in valid_agent_keys:
            raise ValidationError(
                f"Task 'tasks.{task_name}' references unknown agent '{agent_name}'. "
                f"Agent must exist in agents.yaml. Available agents: {sorted(valid_agent_keys)}"
            )


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("Usage: validate_tasks_yaml.py <path/to/tasks.yaml>", file=sys.stderr)
        sys.exit(1)

    path = argv[0]

    try:
        data = load_yaml(path)
        fields = validate_state_fields(data)
        tasks = validate_tasks_block(data)
        validate_task_io(tasks, fields)
        
        # Load and validate agent assignments
        agents_data = load_agents_yaml(path)
        validate_task_agents(tasks, agents_data)
    except ValidationError as e:
        print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Catch-all for unexpected errors
        print(f"UNEXPECTED ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print("YAML validation passed.")


if __name__ == "__main__":
    main()
