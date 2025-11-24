"""Test script for dynamically generated Flow using CrewAI Flow."""

from marketing_crew.flow import (
    CrudTask,
    create_flow_from_tasks
)


def test_dynamic_flow():
    """Test the dynamically generated Flow execution."""
    # Define the workflow tasks
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
    print("Creating dynamic FlowState and Flow classes...")
    FlowStateClass, FlowClass, crew_inputs = create_flow_from_tasks(incoming_tasks)
    
    print(f"\nGenerated FlowState fields: {list(FlowStateClass.model_fields.keys())}")
    print(f"Required context inputs: {crew_inputs['context']}")
    print(f"Required data inputs: {crew_inputs['data']}")
    print(f"All required inputs: {crew_inputs['all']}")
    
    # Create flow instance
    flow = FlowClass()
    
    # Prepare inputs
    inputs = {
        "theme": "SMU Patron's Day 2026",
        "brand_description": "The official Instagram account of Singapore Management University, showcasing campus culture, student life, and signature events with vibrant, youthful storytelling.",
        "target_audience_description": "SMU students, alumni, and the general public in Singapore who enjoy immersive campus festivals, student-generated content, and unique community celebrations.",
        "start_date": "2025-11-01",
        "end_date": "2026-02-21"
    }
    
    print("\nStarting Dynamic Flow execution...")
    print(f"DEBUG: State theme before kickoff: {getattr(flow.state, 'theme', None)}")
    
    # Pass inputs to kickoff() - they will be passed to initialize_flow()
    result = flow.kickoff(inputs=inputs)
    
    print(f"\n{'='*60}")
    print("Flow Execution Complete")
    print(f"{'='*60}")
    print(f"Final result: {result}")
    print(f"\nFinal state summary:")
    flow_id = getattr(flow.state, "flow_id", None)
    run_id = getattr(flow.state, "run_id", None)
    print(f"  Flow ID: {flow_id}")
    print(f"  Run ID: {run_id}")
    
    # Print output field lengths
    for field_name in ["marketing_research", "content_strategy", "social_media_schedule"]:
        value = getattr(flow.state, field_name, None)
        if isinstance(value, str):
            print(f"  {field_name}: {len(value)} chars")
        elif isinstance(value, list):
            print(f"  {field_name}: {len(value)} items")
        else:
            print(f"  {field_name}: {type(value).__name__}")


if __name__ == "__main__":
    test_dynamic_flow()

