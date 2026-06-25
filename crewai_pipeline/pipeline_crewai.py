"""
ClinTranslate v5 — CrewAI Pipeline Orchestrator

Architecture:
  Crew with 5 specialized agents working sequentially.
  Each agent's output feeds the next via CrewAI's context passing.

Key difference vs LangGraph:
  - Agents are given ROLES + GOALS + BACKSTORIES
  - CrewAI manages context passing between tasks
  - Less explicit state management — agents interpret their task via LLM
  - Better for collaborative/open-ended work; less deterministic than LangGraph
"""

import os
import time
import json
from datetime import datetime
from pathlib import Path

from crewai import Crew, Process
from langchain_anthropic import ChatAnthropic

from crewai_pipeline.crew_agents import (
    make_dependency_planner_agent,
    make_rag_translator_agent,
    make_syntax_validator_agent,
    make_confidence_scorer_agent,
    make_report_generator_agent,
)
from crewai_pipeline.crew_tasks import (
    make_dependency_task,
    make_translation_task,
    make_validation_task,
    make_scoring_task,
    make_report_task,
)


def run_crewai_pipeline(sas_folder: str) -> dict:
    """
    Run ClinTranslate via CrewAI sequential crew.
    Returns result dict with output, timing, and metadata.
    """
    start_time = time.time()
    print("\n" + "="*60)
    print("🤖 ClinTranslate v5 — CrewAI Pipeline")
    print(f"   Framework : CrewAI (Sequential Process)")
    print(f"   Input     : {sas_folder}")
    print(f"   Started   : {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)

    # ── LLM setup ─────────────────────────────────────────────────────────────
    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_tokens=2000,
    )

    # ── Agents ────────────────────────────────────────────────────────────────
    print("\n📋 Assembling crew...")
    planner_agent   = make_dependency_planner_agent(llm)
    translator_agent = make_rag_translator_agent(llm)
    validator_agent  = make_syntax_validator_agent(llm)
    scorer_agent     = make_confidence_scorer_agent(llm)
    reporter_agent   = make_report_generator_agent(llm)

    # ── Tasks (sequential context chain) ─────────────────────────────────────
    t1_plan     = make_dependency_task(planner_agent, sas_folder)
    t2_translate = make_translation_task(translator_agent, sas_folder, [t1_plan])
    t3_validate  = make_validation_task(validator_agent, [t2_translate])
    t4_score     = make_scoring_task(scorer_agent, [t3_validate])
    t5_report    = make_report_task(reporter_agent, [t4_score])

    # ── Crew ──────────────────────────────────────────────────────────────────
    crew = Crew(
        agents=[
            planner_agent,
            translator_agent,
            validator_agent,
            scorer_agent,
            reporter_agent,
        ],
        tasks=[t1_plan, t2_translate, t3_validate, t4_score, t5_report],
        process=Process.sequential,   # tasks run in order, output feeds next
        verbose=True,
    )

    # ── Run ───────────────────────────────────────────────────────────────────
    print("\n🚀 Crew is running...\n")
    result = crew.kickoff()
    elapsed = round(time.time() - start_time, 1)

    # ── Save output ───────────────────────────────────────────────────────────
    os.makedirs("reports", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"reports/crewai_report_{ts}.md"

    with open(report_path, "w") as f:
        f.write(f"# ClinTranslate v5 — CrewAI Pipeline Report\n")
        f.write(f"**Run:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Framework:** CrewAI (Sequential)  \n")
        f.write(f"**Total Runtime:** {elapsed}s  \n\n---\n\n")
        f.write(str(result))

    print("\n" + "="*60)
    print(f"✅ CrewAI Pipeline Complete — {elapsed}s total")
    print(f"   Report saved: {report_path}")
    print("="*60)

    return {
        "framework": "CrewAI",
        "process": "Sequential",
        "elapsed_sec": elapsed,
        "report_path": report_path,
        "raw_output": str(result),
    }


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    folder = sys.argv[1] if len(sys.argv) > 1 else "./data/sample_sas"
    run_crewai_pipeline(folder)
