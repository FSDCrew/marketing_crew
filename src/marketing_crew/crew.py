import uuid
from datetime import datetime, timezone
from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from marketing_crew.tools.search import open_page, search_instagram, search_internet

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

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
                open_page,
            ],
            verbose=True,
        )

    @agent
    def content_strategist(self) -> Agent:
        return Agent(
            config=self.agents_config["content_strategist"], # type: ignore[index]
            verbose=True
        )

    @agent
    def visual_creator(self) -> Agent:
        return Agent(
            config=self.agents_config["visual_creator"], # type: ignore[index]
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def copywriter(self) -> Agent:
        return Agent(
            config=self.agents_config["copywriter"], # type: ignore[index]
            verbose=True
        )
        
    @task
    def market_research(self) -> Task:
        return Task(
            config=self.tasks_config["market_research"], # type: ignore[index]
            agent=self.market_researcher(),
            output_file="output/market_research.md",
        )

    @task
    def content_strategy_task(self) -> Task:
        return Task(
            config=self.tasks_config["content_strategy"], # type: ignore[index]
            agent=self.content_strategist(),
        )

    @task
    def visual_content_creation_task(self) -> Task:
        return Task(
            config=self.tasks_config["visual_content_creation"], # type: ignore[index]
            agent=self.visual_creator(),
            output_file="output/visual-content.md",
        )

    @task
    def copywriting_task(self) -> Task:
        return Task(
            config=self.tasks_config["copywriting"], # type: ignore[index]
            agent=self.copywriter(),
        )

    @task
    def report_final_content_strategy(self) -> Task:
        return Task(
            config=self.tasks_config["report_final_content_strategy"], # type: ignore[index]
            agent=self.content_strategist(),
            output_file="output/final-content-strategy.md",
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
        )
