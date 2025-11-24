import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

# from aiohttp import tracing
from crewai import Agent, Crew, LLM, Process, Task, TaskOutput
from crewai.flow.flow import Flow, listen, start
from crewai.project import CrewBase, agent, crew, task
from pydantic import BaseModel, Field
from litellm import BaseModel as LiteLLMBaseModel

from marketing_crew.tools.html_to_excel import html_to_excel_tool
from marketing_crew.tools.markdown_to_word import markdown_to_word_doc
from marketing_crew.tools.open_instagram_posts import open_instagram_posts
from marketing_crew.tools.search import open_pages, search_instagram, search_internet


# ============================================================================
# LLM Configuration
# ============================================================================

function_calling_llm = LLM(
    model="openai/gpt-4o-mini",
)

general_llm = LLM(
    # model="openai/gpt-4.1-mini",
    model="openai/gpt-4o-mini",
    temperature=0.7,
    seed=42
)


class GuardrailResponseFormat(LiteLLMBaseModel):
    valid: bool
    reason: str


judge_llm = LLM(
    model="openai/gpt-4.1-mini",
    temperature=0.7,
    response_format=GuardrailResponseFormat,
    seed=42
)
   
def llm_judge_guardrail(output: TaskOutput) -> Tuple[bool, Any]:
    """Use LLM as a judge to validate task output."""
    try:
        evaluation_prompt = (
            "<task_expected_output>\n" + str(output.expected_output) + "\n</task_expected_output>\n\n"
            "<task_actual_output>\n" + str(output.raw) + "\n</task_actual_output>\n\n"
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
        
        if not parsed.valid:
            raise Exception(f"Evaluation failed: {parsed.reason}")
        return (parsed.valid, output.raw)

    except Exception as e:
        raise Exception(f"Evaluation error: {str(e)}")


# ============================================================================
# Flow State Definition
# ============================================================================

class MarketingFlowState(BaseModel):
    """Structured state for the marketing campaign flow.
    
    This state contains all possible inputs and outputs for the workflow.
    Each task reads from and writes to specific fields in this state.
    """
    # Input fields (provided by user or upstream tasks)
    theme: Optional[str] = None
    brand_description: Optional[str] = None
    target_audience_description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    # Output fields (produced by tasks)
    marketing_research: Optional[str] = None
    content_strategy: Optional[str] = None
    social_media_schedule: Optional[str] = None
    
    # Metadata
    flow_id: Optional[str] = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    run_id: Optional[str] = None


# ============================================================================
# Flow Implementation
# ============================================================================

class MarketingFlow(Flow[MarketingFlowState]):
    """Marketing campaign workflow using CrewAI Flow.
    
    Each step in the flow:
    1. Reads required inputs from self.state
    2. Creates a Crew with one Task
    3. Executes the crew
    4. Writes outputs back to self.state
    """
    def __init__(self):
        super().__init__(tracing=True)

    @start()
    def initialize_flow(self, inputs: Optional[dict] = None):
        """Initialize the flow with user inputs and metadata."""
        print("\n ###### Initializing flow ######")
        # Set state values from inputs if provided
        if inputs:
            self.state.theme = inputs.get("theme")
            self.state.brand_description = inputs.get("brand_description")
            self.state.target_audience_description = inputs.get("target_audience_description")
            self.state.start_date = inputs.get("start_date")
            self.state.end_date = inputs.get("end_date")
        
        # Generate run ID for logging
        if not self.state.run_id:
            self.state.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        
        print(f"Initializing Marketing Flow")
        print(f"Flow ID: {self.state.flow_id}")
        print(f"Run ID: {self.state.run_id}")
        print(f"Theme: {self.state.theme}")
        
        # Validate required inputs
        if not self.state.theme:
            raise ValueError("theme is required")
        if not self.state.brand_description:
            raise ValueError("brand_description is required")
        if not self.state.target_audience_description:
            raise ValueError("target_audience_description is required")
        if not self.state.start_date:
            raise ValueError("start_date is required")
        if not self.state.end_date:
            raise ValueError("end_date is required")
        
        return "Flow initialized"

    @listen(initialize_flow)
    def marketing_research(self, previous_result: str):
        """Step 1: Perform market research.
        
        Required inputs from state:
        - theme
        - brand_description
        - target_audience_description
        - start_date
        - end_date
        
        Produces outputs:
        - marketing_research
        """
        print(f"\n{'='*60}")
        print("Step 1: Marketing Research")
        print(f"{'='*60}")
        print(f"Previous step: {previous_result}")
        
        # Read inputs from state
        theme = self.state.theme
        brand_description = self.state.brand_description
        target_audience_description = self.state.target_audience_description
        start_date = self.state.start_date
        end_date = self.state.end_date
        
        # Prepare task inputs
        @CrewBase
        class MarketingResearchCrew():
            @agent
            def market_researcher(self) -> Agent:
                return Agent(
                    config=self.agents_config["market_researcher"],  # type: ignore[index]
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

                
            @task
            def marketing_research_task(self) -> Task:
                return Task(
                    config=self.tasks_config["marketing_research"],  # type: ignore[index]
                    agent=self.market_researcher(),
                    output_file="output/preparing_marketing_campaign/market_research.md",
                    guardrail=llm_judge_guardrail,
                    guardrail_max_retries=3
                )
            
            @crew
            def crew(self) -> Crew:
                return Crew(
                    agents=[self.market_researcher()],
                    tasks=[self.marketing_research_task()],
                    process=Process.sequential,
                    verbose=True,
                    function_calling_llm=function_calling_llm
                )
            
            
        research_crew = MarketingResearchCrew().crew()
        result = research_crew.kickoff(inputs={
            'theme': theme,
            'brand_description': brand_description,
            'target_audience_description': target_audience_description,
            'start_date': start_date,
            'end_date': end_date
        })
        self.state.marketing_research = result.raw
        return "Marketing research completed"

    # @listen(marketing_research)
    # def content_strategy(self, previous_result: str):
    #     """Step 2: Develop content strategy.
        
    #     Required inputs from state:
    #     - brand_description
    #     - target_audience_description
    #     - start_date
    #     - end_date
    #     - marketing_research (from previous step)
        
    #     Produces outputs:
    #     - content_strategy
    #     """
    #     print(f"\n{'='*60}")
    #     print("Step 2: Content Strategy")
    #     print(f"{'='*60}")
    #     print(f"Previous step: {previous_result}")
        
    #     # Validate required inputs
    #     if not self.state.marketing_research:
    #         raise ValueError("marketing_research is required but not available in state")
        
    #     # Read inputs from state
    #     brand_description = self.state.brand_description
    #     target_audience_description = self.state.target_audience_description
    #     start_date = self.state.start_date
    #     end_date = self.state.end_date
        
    #     # Prepare task inputs
    #     task_inputs = {
    #         'brand_description': brand_description,
    #         'target_audience_description': target_audience_description,
    #         'start_date': start_date,
    #         'end_date': end_date,
    #         'marketing_research': self.state.marketing_research
    #     }
        
    #     @CrewBase
    #     class ContentStrategyCrew():
    #         @agent
    #         def content_strategist(self) -> Agent:
    #             return Agent(
    #                 config=self.agents_config["content_strategist"],  # type: ignore[index]
    #                 verbose=True,
    #                 llm=general_llm
    #             )
            
    #         @task
    #         def content_strategy_task(self) -> Task:
    #             return Task(
    #                 config=self.tasks_config["content_strategy"],  # type: ignore[index]
    #                 agent=self.content_strategist(),
    #                 output_file="output/preparing_marketing_campaign/content_strategy.md",
    #                 guardrail=llm_judge_guardrail,
    #                 guardrail_max_retries=3,
    #             )
            
    #         @crew
    #         def crew(self) -> Crew:
    #             return Crew(
    #                 agents=[self.content_strategist()],
    #                 tasks=[self.content_strategy_task()],
    #                 process=Process.sequential,
    #                 verbose=True,
    #                 function_calling_llm=function_calling_llm
    #             )
            
    #     strategy_crew = ContentStrategyCrew().crew()
    #     result = strategy_crew.kickoff(inputs=task_inputs)
    #     self.state.content_strategy = result.raw
    #     return "Content strategy completed"

    # @listen(content_strategy)
    # def social_media_schedule(self, previous_result: str):
    #     """Step 3: Create social media schedule.
        
    #     Required inputs from state:
    #     - brand_description
    #     - target_audience_description
    #     - start_date
    #     - end_date
    #     - content_strategy (from previous step)
        
    #     Produces outputs:
    #     - social_media_schedule
    #     """
    #     print(f"\n{'='*60}")
    #     print("Step 3: Social Media Schedule")
    #     print(f"{'='*60}")
    #     print(f"Previous step: {previous_result}")
        
    #     # Validate required inputs
    #     if not self.state.content_strategy:
    #         raise ValueError("content_strategy is required but not available in state")
        
    #     # Read inputs from state
    #     brand_description = self.state.brand_description
    #     target_audience_description = self.state.target_audience_description
    #     start_date = self.state.start_date
    #     end_date = self.state.end_date
        
    #     # Prepare task inputs
    #     task_inputs = {
    #         'brand_description': brand_description,
    #         'target_audience_description': target_audience_description,
    #         'start_date': start_date,
    #         'end_date': end_date,
    #         'marketing_research': self.state.marketing_research,
    #         'content_strategy': self.state.content_strategy
    #     }
        
    #     @CrewBase
    #     class SocialMediaScheduleCrew():
    #         @agent
    #         def scheduler(self) -> Agent:
    #             return Agent(
    #                 config=self.agents_config["scheduler"],  # type: ignore[index]
    #                 tools=[html_to_excel_tool],
    #                 verbose=True,
    #                 llm=general_llm
    #             )
            
    #         @task
    #         def social_media_schedule_task(self) -> Task:
    #             return Task(
    #                 config=self.tasks_config["social_media_schedule"],  # type: ignore[index]
    #                 agent=self.scheduler(),
    #                 output_file="output/preparing_marketing_campaign/social_media_schedule.md",
    #                 guardrail=llm_judge_guardrail,
    #                 guardrail_max_retries=3,
    #             )       
            
    #         @crew
    #         def crew(self) -> Crew:
    #             return Crew(
    #                 agents=[self.scheduler()],
    #                 tasks=[self.social_media_schedule_task()],
    #                 process=Process.sequential,
    #                 verbose=True,
    #                 function_calling_llm=function_calling_llm
    #             )
        
    #     schedule_crew = SocialMediaScheduleCrew().crew()
    #     result = schedule_crew.kickoff(inputs=task_inputs)
    #     self.state.social_media_schedule = result.raw
    #     return "Social media schedule completed"

