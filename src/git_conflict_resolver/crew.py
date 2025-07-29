from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from git_conflict_resolver.tools.git_conflict_finder_tool import GitConflictFinderTool
from git_conflict_resolver.tools.git_conflict_resolver_tool import GitConflictResolverTool
from typing import List
import os
import agentops

agentops.init(
        default_tags=['crewai']
)

gemini_llm = LLM(
    model="gemini/gemini-2.0-flash-001",
    api_key=os.environ.get("GEMINI_API_KEY"),
    temperature=0
)

@CrewBase
class GitConflictResolverCrew:
    agents_config = 'config/agents.yaml'  # Add this
    tasks_config = 'config/tasks.yaml'    # Add this

    @agent
    def conflict_detector(self) -> Agent:
        return Agent(
            config=self.agents_config['conflict_detector'],
            tools=[GitConflictFinderTool()],
            llm=gemini_llm,
            verbose=True
        )

    @agent
    def conflict_resolver(self) -> Agent:
        return Agent(
            config=self.agents_config['conflict_resolver'],
            tools=[GitConflictResolverTool()],
            llm=gemini_llm,
            verbose=True
        )

    @agent
    def summary_reporter(self) -> Agent:
        return Agent(
            config=self.agents_config['summary_reporter'],
            llm=gemini_llm,
            verbose=True
        )

    @agent
    def manager(self) -> Agent:
        return Agent(
            config=self.agents_config['manager'],
            llm=gemini_llm,
            verbose=True,
            allow_delegation=True
        )

    @task
    def detect_conflicts_task(self) -> Task:
        return Task(config=self.tasks_config['detect_conflicts_task'])

    @task
    def resolve_conflicts_task(self) -> Task:
        return Task(config=self.tasks_config['resolve_conflicts_task'])

    @task
    def summary_task(self) -> Task:
        return Task(config=self.tasks_config['summary_task'])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.conflict_detector(), self.conflict_resolver(), self.summary_reporter()],  
            tasks=self.tasks,
            manager_agent=self.manager(),  # Manager is separate
            process=Process.hierarchical,
            verbose=True
        )