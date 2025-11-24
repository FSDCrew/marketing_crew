#!/usr/bin/env python
"""Test script for MarketingFlow using CrewAI Flow."""

from marketing_crew.flow import MarketingFlow, MarketingFlowState


def test_flow():
    """Test the MarketingFlow execution."""
    # Create flow instance
    flow = MarketingFlow()
    
    # Prepare inputs dictionary to pass to kickoff()
    inputs = {
        "theme": "SMU Patron's Day 2026",
        "brand_description": "The official Instagram account of Singapore Management University, showcasing campus culture, student life, and signature events with vibrant, youthful storytelling.",
        "target_audience_description": "SMU students, alumni, and the general public in Singapore who enjoy immersive campus festivals, student-generated content, and unique community celebrations.",
        "start_date": "2025-11-01",
        "end_date": "2026-02-21"
    }
    
    print("Starting Marketing Flow execution...")
    print(f"DEBUG: State theme before kickoff: {flow.state.theme}")
    # Pass inputs to kickoff() - they will be passed to initialize_flow()
    result = flow.kickoff(inputs=inputs)

    print(f"\n{'='*60}")
    print("Flow Execution Complete")
    print(f"{'='*60}")
    print(f"Final result: {result}")
    print(f"\nFinal state summary:")
    print(f"  Flow ID: {flow.state.flow_id}")
    print(f"  Run ID: {flow.state.run_id}")
    print(f"  Marketing research: {len(flow.state.marketing_research or '')} chars")
    print(f"  Content strategy: {len(flow.state.content_strategy or '')} chars")
    print(f"  Social media schedule: {len(flow.state.social_media_schedule or '')} chars")


if __name__ == "__main__":
    test_flow()

