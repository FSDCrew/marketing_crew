#!/usr/bin/env python
import sys
import warnings

from datetime import datetime

from marketing_crew.crew import MarketingCrew

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew.
    """
    inputs = {
        'theme': "SMU Patron's Day 2026",
        'brand_description': "The official Instagram account of Singapore Management University, showcasing campus culture, student life, and signature events with vibrant, youthful storytelling.",
        'target_audience_description': "SMU students, alumni, and the general public in Singapore who enjoy immersive campus festivals, student-generated content, and unique community celebrations.",
        'start_date': "2025-11-01",
        'end_date': "2026-02-21"
    }

    try:
        result = MarketingCrew().crew().kickoff(inputs=inputs)
        print(f"\nCrew Output:\n{result.raw}")
        print(f"\nToken Usage:\n{result.token_usage}")
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "topic": "AI LLMs",
        'current_year': str(datetime.now().year)
    }
    try:
        MarketingCrew().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        MarketingCrew().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }
    
    try:
        MarketingCrew().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
