import uuid
from datetime import datetime, timezone
from typing import Any, List, Tuple

from crewai import Agent, Crew, LLM, Process, Task, TaskOutput
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from litellm import BaseModel

from marketing_crew.tools.html_to_excel import html_to_excel_tool
from marketing_crew.tools.markdown_to_word import markdown_to_word_doc
from marketing_crew.tools.open_instagram_posts import open_instagram_posts
from marketing_crew.tools.search import open_pages, search_instagram, search_internet
from crewai_tools import FileWriterTool


# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

function_calling_llm = LLM(
    model="openai/gpt-4o-mini",
)

# general_llm = LLM(
#     model="openai/gpt-4o-mini",
#     temperature=0.7,
#     seed=42
# )

general_llm=LLM(
    model="openai/gpt-4.1-mini",
    temperature=0.7,
    seed=42
)

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

@CrewBase
class MarketingCrew():
    """MarketingCrew crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def market_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["market_researcher"], # type: ignore[index]
            tools=[
                search_internet,
                search_instagram,
                open_pages,
                open_instagram_posts,
                markdown_to_word_doc,
            ],
            verbose=True,
            llm=general_llm
        )

    @agent
    def content_strategist(self) -> Agent:
        return Agent(
            config=self.agents_config["content_strategist"], # type: ignore[index]
            verbose=True,
            llm=general_llm
        )
        
    @agent
    def scheduler(self) -> Agent:
        return Agent(
            config=self.agents_config["scheduler"], # type: ignore[index]
            tools=[
                html_to_excel_tool,
            ],
            verbose=True,
            llm=general_llm
        )
        
    @task
    def marketing_research_task(self) -> Task:
        return Task(
            config=self.tasks_config["marketing_research"], # type: ignore[index]
            agent=self.market_researcher(),
            output_file="output/preparing_marketing_campaign/market_research.md",
            guardrail=llm_judge_guardrail,
            guardrail_max_retries=3
        )

    @task
    def content_strategy_task(self) -> Task:
        return Task(
            config=self.tasks_config["content_strategy"], # type: ignore[index]
            agent=self.content_strategist(),
            output_file="output/preparing_marketing_campaign/content_strategy.md",
            guardrail=llm_judge_guardrail,
            guardrail_max_retries=3
        )

    @task
    def social_media_scheduler_task(self) -> Task:
        return Task(
            config=self.tasks_config["social_media_schedule"], # type: ignore[index]
            agent=self.scheduler(),
            output_file="output/preparing_marketing_campaign/social_media_schedule.md",
            guardrail=llm_judge_guardrail,
            guardrail_max_retries=3
        )

    @crew
    def crew(self) -> Crew:
        """Creates the MarketingCrew crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge
        
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        short_uuid = uuid.uuid4().hex[:8]
        log_path = f'logs/crewrun_{run_id}_{short_uuid}.json'


        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            output_log_file=log_path,
            process=Process.sequential,
            verbose=True,
            function_calling_llm=function_calling_llm
        )
