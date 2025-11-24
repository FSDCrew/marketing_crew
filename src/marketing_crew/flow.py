import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type

import yaml
from pydantic import BaseModel, Field, create_model
from crewai import Agent as CrewAIAgent, Task as CrewAITask, Crew, LLM, Process, TaskOutput
from crewai.flow.flow import Flow, listen, start

from marketing_crew.tools.html_to_excel import html_to_excel_tool
from marketing_crew.tools.markdown_to_word import markdown_to_word_doc
from marketing_crew.tools.open_instagram_posts import open_instagram_posts
from marketing_crew.tools.search import open_pages, search_internet, search_instagram

general_llm = LLM(
    model="openai/gpt-4.1-mini",
    # model="openai/gpt-4o-mini",
    temperature=0.7,
    seed=42
)

function_calling_llm = LLM(
    model="openai/gpt-4o-mini",
)

TOOL_MAP = {
    "search_internet": search_internet,
    "search_instagram": search_instagram,
    "open_pages": open_pages,
    "open_instagram_post_page": open_instagram_posts,
    "open_instagram_posts": open_instagram_posts,
    "markdown_to_word_doc": markdown_to_word_doc,
    "html_to_excel": html_to_excel_tool,
}

class CrudTask(BaseModel):
    key: str
    agent_key: str
    order: int
    
class GuardrailResponseFormat(BaseModel):
    valid: bool
    reason: str 
    
judge_llm = LLM(
    model="openai/gpt-4.1-mini", 
    temperature=0.7,
    response_format=GuardrailResponseFormat,
    seed=42
)

def llm_judge_guardrail(result: TaskOutput) -> Tuple[bool, Any]:
    """Use LLM as a judge to validate task output."""
    try:
        evaluation_prompt = (
            # "<task_description>\n" + str(result.description) + "\n</task_description>\n\n"
            "<task_expected_output>\n" + str(result.expected_output) + "\n</task_expected_output>\n\n"
            "<task_actual_output>\n" + str(result.raw) + "\n</task_actual_output>\n\n"
            "<your_task>\n"
            "Evaluate if the actual output meets the task requirements.\n"
            "Respond ONLY with JSON format.\n"
            "{\n"
            '    "valid": boolean,\n'
            '    "reason": string\n'
            "}\n"
            "</your_task>\n"
        )
        
        response = judge_llm.call([{"role": "user", "content": evaluation_prompt}])
        
        if isinstance(response, str):
            parsed = GuardrailResponseFormat.model_validate_json(response)
        elif isinstance(response, dict):
            parsed = GuardrailResponseFormat.model_validate(response)
        else:
            parsed = response
            
        print(f"\nEvaluation Response: {parsed.valid} - Reason: {parsed.reason}") # ! Debugging
        return (parsed.valid, parsed.reason)
            
    except Exception as e:
        raise Exception(f"Evaluation error: {str(e)}")

def load_yaml_config(file_path: Path) -> Dict[str, Any]:
    """Load a YAML configuration file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_config_path() -> Path:
    """Get the path to the config directory."""
    current_file = Path(__file__).resolve()
    config_dir = current_file.parent / "config"
    return config_dir


def get_tools_from_agent_config(agent_config: Dict[str, Any]) -> List[Any]:
    """Extract tool objects from agent config based on tool names."""
    tools = []
    tool_names = agent_config.get("tools", [])
    
    if not isinstance(tool_names, list):
        return tools
    
    for tool_name in tool_names:
        if isinstance(tool_name, str) and tool_name in TOOL_MAP:
            tool_obj = TOOL_MAP[tool_name]
            if tool_obj not in tools:
                tools.append(tool_obj)
    
    return tools


def create_crewai_agents(
    agents_data: Dict[str, Any]
) -> Dict[str, CrewAIAgent]:
    """Convert Task objects and YAML configs to CrewAI Agent instances."""
    agents = {}
    
    for agent_key, agent_config in agents_data.items():
        tools = get_tools_from_agent_config(agent_config)
        
        agents[agent_key] = CrewAIAgent(
            role=agent_config.get("role", ""),
            goal=agent_config.get("goal", ""),
            backstory=agent_config.get("backstory", ""),
            tools=tools if tools else None,
            verbose=True,
            llm=general_llm
        )
    
    return agents


def create_crewai_tasks(
    tasks: List[CrudTask],
    tasks_data: Dict[str, Any],
    agents: Dict[str, CrewAIAgent]
) -> List[CrewAITask]:
    """Convert CrudTask objects and YAML configs to CrewAI Task instances."""
    tasks_dict = tasks_data.get("tasks", {})
    crewai_tasks = []
    
    for task_obj in tasks:
        task_key = task_obj.key
        agent_key = task_obj.agent_key
        
        if task_key not in tasks_dict or agent_key not in agents:
            continue
        
        task_config = tasks_dict[task_key]
        agent = agents[agent_key]
        
        crewai_task = CrewAITask(
            description=task_config.get("description", ""),
            expected_output=task_config.get("expected_output", ""),
            **({"output_file": task_config["output_file"]} if "output_file" in task_config else {}),
            agent=agent,
            guardrail=llm_judge_guardrail,
            guardrail_max_retries=3
        )
        
        crewai_tasks.append(crewai_task)
    
    return crewai_tasks


# ============================================================================
# Workflow Metadata Compilation
# ============================================================================

class WorkflowMetadata:
    """Compiled metadata about the workflow structure."""
    
    def __init__(self):
        self.field_producers: Dict[str, List[str]] = {}  # field -> list of task keys that write it
        self.field_consumers: Dict[str, List[str]] = {}  # field -> list of task keys that read it
        self.task_reads: Dict[str, List[Dict[str, Any]]] = {}  # task_key -> list of read definitions
        self.task_writes: Dict[str, List[Dict[str, Any]]] = {}  # task_key -> list of write definitions
        self.state_fields: Dict[str, Dict[str, Any]] = {}  # field_name -> field definition
        self.all_fields: Set[str] = set()
    
    def add_field(self, field_name: str, field_def: Dict[str, Any]):
        """Add a state field definition."""
        self.state_fields[field_name] = field_def
        self.all_fields.add(field_name)
        if field_name not in self.field_producers:
            self.field_producers[field_name] = []
        if field_name not in self.field_consumers:
            self.field_consumers[field_name] = []
    
    def add_task_read(self, task_key: str, read_def: Dict[str, Any]):
        """Record that a task reads a field."""
        field_name = read_def["field"]
        if task_key not in self.task_reads:
            self.task_reads[task_key] = []
        self.task_reads[task_key].append(read_def)
        self.field_consumers[field_name].append(task_key)
        self.all_fields.add(field_name)
    
    def add_task_write(self, task_key: str, write_def: Dict[str, Any]):
        """Record that a task writes a field."""
        field_name = write_def["field"]
        if task_key not in self.task_writes:
            self.task_writes[task_key] = []
        self.task_writes[task_key].append(write_def)
        self.field_producers[field_name].append(task_key)
        self.all_fields.add(field_name)


def compile_workflow_metadata(
    incoming_tasks: List[CrudTask],
    tasks_data: Dict[str, Any]
) -> WorkflowMetadata:
    """Compile workflow metadata from tasks and YAML definitions."""
    metadata = WorkflowMetadata()
    
    # Load state fields
    state_fields = tasks_data.get("state", {}).get("fields", {})
    for field_name, field_def in state_fields.items():
        metadata.add_field(field_name, field_def)
    
    # Process each task
    tasks_dict = tasks_data.get("tasks", {})
    for task_obj in incoming_tasks:
        task_key = task_obj.key
        if task_key not in tasks_dict:
            continue
        
        task_config = tasks_dict[task_key]
        
        # Process reads
        reads = task_config.get("reads", [])
        for read_def in reads:
            metadata.add_task_read(task_key, read_def)
        
        # Process writes
        writes = task_config.get("writes", [])
        for write_def in writes:
            metadata.add_task_write(task_key, write_def)
    
    return metadata


def determine_crew_inputs(
    metadata: WorkflowMetadata,
    incoming_tasks: List[CrudTask]
) -> Dict[str, List[str]]:
    """Determine which fields need to be provided by the user (crew inputs)."""
    context_inputs = []
    data_inputs = []
    
    task_keys = {task.key for task in incoming_tasks}
    
    # A. Context Crew Inputs
    for field_name, field_def in metadata.state_fields.items():
        if field_def.get("field_kind") == "context":
            # Check if any task reads this field
            consumers = metadata.field_consumers.get(field_name, [])
            if any(consumer in task_keys for consumer in consumers):
                context_inputs.append(field_name)
    
    # B. Data Crew Inputs
    for field_name, field_def in metadata.state_fields.items():
        if field_def.get("field_kind") == "data":
            # Check if any task requires this field
            requires_field = False
            for task_key in task_keys:
                reads = metadata.task_reads.get(task_key, [])
                for read_def in reads:
                    if read_def["field"] == field_name:
                        cardinality = read_def.get("cardinality", "required")
                        if cardinality == "required":
                            requires_field = True
                            break
                if requires_field:
                    break
            
            if requires_field:
                # Check if any upstream task produces it
                producers = metadata.field_producers.get(field_name, [])
                if not any(producer in task_keys for producer in producers):
                    data_inputs.append(field_name)
    
    return {
        "context": context_inputs,
        "data": data_inputs,
        "all": context_inputs + data_inputs
    }


# ============================================================================
# Dynamic FlowState Generation
# ============================================================================

def get_python_type_from_field_type(field_type: str) -> Type:
    """Convert YAML field type to Python type."""
    type_mapping = {
        "string": str,
        "date": str,  # Dates stored as strings
        "int": int,
        "float": float,
        "bool": bool,
    }
    
    # Handle list types
    if field_type.startswith("list[") or field_type.startswith("List["):
        return List[Any]
    
    return type_mapping.get(field_type.lower(), str)


def create_flow_state_class(metadata: WorkflowMetadata) -> Type[BaseModel]:
    """Dynamically create a FlowState Pydantic model from metadata."""
    field_definitions = {}
    
    # Add flow_id and run_id metadata fields
    field_definitions["flow_id"] = (Optional[str], Field(default_factory=lambda: uuid.uuid4().hex[:8]))
    field_definitions["run_id"] = (Optional[str], None)
    
    # Add all state fields
    for field_name, field_def in metadata.state_fields.items():
        field_type_str = field_def.get("type", "string")
        python_type = get_python_type_from_field_type(field_type_str)
        
        # Determine default value
        if field_type_str.startswith("list[") or field_type_str.startswith("List["):
            default_value = []
        else:
            default_value = None
        
        field_definitions[field_name] = (Optional[python_type], default_value)
    
    # Create the model dynamically
    FlowStateModel = create_model(
        "FlowState",
        __base__=BaseModel,
        **field_definitions
    )
    
    return FlowStateModel


# ============================================================================
# Dynamic Flow Generation
# ============================================================================

def format_task_description(description: str, state_values: Dict[str, Any]) -> str:
    """Format task description by replacing {field_name} placeholders with state values."""
    formatted = description
    for field_name, value in state_values.items():
        placeholder = f"{{{field_name}}}"
        if placeholder in formatted:
            formatted = formatted.replace(placeholder, str(value) if value is not None else "")
    return formatted


def create_task_step_method(
    task_obj: CrudTask,
    step_index: int,
    tasks_data: Dict[str, Any],
    crewai_agents: Dict[str, CrewAIAgent],
    metadata: WorkflowMetadata
):
    """Create a flow step method function for a specific task."""
    task_key = task_obj.key
    agent_key = task_obj.agent_key
    
    def step_method(self_ref, previous_result: str):
        """Execute a single task step."""
        print(f"\n{'='*60}")
        print(f"Step {step_index + 1}: {task_key}")
        print(f"{'='*60}")
        print(f"Previous step: {previous_result}")
        
        # Get task config
        tasks_dict = tasks_data.get("tasks", {})
        task_config = tasks_dict.get(task_key, {})
        
        # Read inputs from state based on task's reads
        task_inputs = {}
        reads = metadata.task_reads.get(task_key, [])
        
        for read_def in reads:
            field_name = read_def["field"]
            cardinality = read_def.get("cardinality", "required")
            
            # Get value from state
            value = getattr(self_ref.state, field_name, None)
            
            # Validate cardinality
            if cardinality == "required" and value is None:
                raise ValueError(f"{field_name} is required for task {task_key} but is not available in state")
            elif cardinality == "at_least_one":
                if not isinstance(value, list) or len(value) == 0:
                    raise ValueError(f"{field_name} must contain at least one item for task {task_key}")
            
            if value is not None:
                task_inputs[field_name] = value
        
        # Format task description with state values
        description = task_config.get("description", "")
        formatted_description = format_task_description(description, task_inputs)
        
        # Create Crew with single Task
        agent = crewai_agents.get(agent_key)
        if not agent:
            raise ValueError(f"Agent {agent_key} not found")
        
        # Create CrewAI Task
        crewai_task = CrewAITask(
            description=formatted_description,
            expected_output=task_config.get("expected_output", ""),
            agent=agent
        )
        
        # Create Crew
        crew_instance = Crew(
            agents=[agent],
            tasks=[crewai_task],
            process=Process.sequential,
            verbose=True,
            function_calling_llm=function_calling_llm
        )
        
        # Execute crew
        result = crew_instance.kickoff(inputs=task_inputs)
        
        # Write outputs back to state based on task's writes
        writes = metadata.task_writes.get(task_key, [])
        for write_def in writes:
            field_name = write_def["field"]
            mode = write_def.get("mode", "replace")
            
            if mode == "replace":
                setattr(self_ref.state, field_name, result.raw)
            elif mode == "append":
                current_value = getattr(self_ref.state, field_name, [])
                if not isinstance(current_value, list):
                    current_value = []
                if isinstance(result.raw, list):
                    current_value.extend(result.raw)
                else:
                    current_value.append(result.raw)
                setattr(self_ref.state, field_name, current_value)
        
        return f"{task_key} completed"
    
    return step_method


def create_dynamic_flow_class(
    FlowStateClass: Type[BaseModel],
    incoming_tasks: List[CrudTask],
    tasks_data: Dict[str, Any],
    agents_data: Dict[str, Any],
    crewai_agents: Dict[str, CrewAIAgent],
    metadata: WorkflowMetadata
) -> Type[Flow]:
    """Dynamically create a Flow class with steps for each task."""
    
    # Define initialize_flow method
    def initialize_flow(self, inputs: Optional[dict] = None):
        """Initialize the flow with user inputs and metadata."""
        print("\n ###### Initializing flow ######")
        
        # Set state values from inputs if provided
        if inputs:
            for field_name, value in inputs.items():
                if hasattr(self.state, field_name):
                    setattr(self.state, field_name, value)
        
        # Generate run ID for logging
        run_id = getattr(self.state, "run_id", None)
        if not run_id:
            run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            setattr(self.state, "run_id", run_id)
        
        print(f"Initializing Dynamic Flow")
        flow_id = getattr(self.state, "flow_id", None)
        print(f"Flow ID: {flow_id}")
        print(f"Run ID: {run_id}")
        
        # Validate required context inputs
        for field_name, field_def in self.metadata.state_fields.items():
            if field_def.get("field_kind") == "context":
                value = getattr(self.state, field_name, None)
                if not value:
                    raise ValueError(f"{field_name} is required")
        
        return "Flow initialized"
    
    # Apply @start decorator to initialize_flow
    initialize_flow = start()(initialize_flow)
    
    # Create all step methods first
    step_methods = {}
    for i, task_obj in enumerate(incoming_tasks):
        step_method = create_task_step_method(
            task_obj, i, tasks_data, crewai_agents, metadata
        )
        step_method.__name__ = f"step_{task_obj.key}"
        step_methods[task_obj.key] = step_method
    
    # Define __init__ method
    def __init__(self):
        Flow.__init__(self, tracing=True)
        self.tasks_data = tasks_data
        self.agents_data = agents_data
        self.crewai_agents = crewai_agents
        self.metadata = metadata
    
    # Build class dictionary with all methods
    class_dict = {
        "__init__": __init__,
        "initialize_flow": initialize_flow,
    }
    
    # Apply @listen decorators in order and add to class_dict
    # Use string method names for reliability
    for i, task_obj in enumerate(incoming_tasks):
        step_method = step_methods[task_obj.key]
        
        # Apply @listen decorator using string method names
        if i == 0:
            # First step listens to initialize_flow by name
            decorated_method = listen("initialize_flow")(step_method)
        else:
            # Subsequent steps listen to the previous step method by name
            prev_task_key = incoming_tasks[i-1].key
            prev_method_name = f"step_{prev_task_key}"
            decorated_method = listen(prev_method_name)(step_method)
        
        method_name = f"step_{task_obj.key}"
        class_dict[method_name] = decorated_method
    
    # Create the class using type()
    DynamicFlow = type(
        "DynamicFlow",
        (Flow[FlowStateClass],),
        class_dict
    )
    
    return DynamicFlow


# ============================================================================
# Main Flow Factory Function
# ============================================================================

def create_flow_from_tasks(
    incoming_tasks: List[CrudTask],
    tasks_data: Optional[Dict[str, Any]] = None,
    agents_data: Optional[Dict[str, Any]] = None
) -> Tuple[Type[BaseModel], Type[Flow], Dict[str, List[str]]]:
    """Create FlowState and Flow classes from task definitions.
    
    Returns:
        tuple: (FlowStateClass, FlowClass, crew_inputs)
    """
    # Load configs if not provided
    if tasks_data is None or agents_data is None:
        config_dir = get_config_path()
        if tasks_data is None:
            tasks_data = load_yaml_config(config_dir / "tasks.yaml")
        if agents_data is None:
            agents_data = load_yaml_config(config_dir / "agents.yaml")
    
    # Compile workflow metadata
    metadata = compile_workflow_metadata(incoming_tasks, tasks_data)
    
    # Determine crew inputs
    crew_inputs = determine_crew_inputs(metadata, incoming_tasks)
    
    # Create agents
    crewai_agents = create_crewai_agents(agents_data)
    
    # Create FlowState class
    FlowStateClass = create_flow_state_class(metadata)
    
    # Create Flow class
    FlowClass = create_dynamic_flow_class(
        FlowStateClass,
        incoming_tasks,
        tasks_data,
        agents_data,
        crewai_agents,
        metadata
    )
    
    return FlowStateClass, FlowClass, crew_inputs


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example: Create flow from incoming tasks
    incoming_tasks = [
        CrudTask(
            key="marketing_research",
            agent_key="market_researcher",
            order=1
        ),
        CrudTask(
            key="content_strategy",
            agent_key="content_strategist",
            order=2
        ),
        CrudTask(
            key="social_media_schedule",
            agent_key="scheduler",
            order=3
        )
    ]
    
    # Create FlowState and Flow classes dynamically
    FlowStateClass, FlowClass, crew_inputs = create_flow_from_tasks(incoming_tasks)
    
    print("Generated FlowState fields:", list(FlowStateClass.model_fields.keys()))
    print("Required crew inputs:", crew_inputs["all"])
    
    # Create flow instance
    flow = FlowClass()
    
    # Prepare inputs
    inputs = {
        "theme": "SMU Patron's Day 2026",
        "brand_description": "The official Instagram account of Singapore Management University",
        "target_audience_description": "SMU students, alumni, and the general public",
        "start_date": "2025-11-01",
        "end_date": "2026-02-21"
    }
    
    # Run the flow
    # result = flow.kickoff(inputs=inputs)
    # print(f"Final state: {flow.state}")