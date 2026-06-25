"""
ClinTranslate v5 — CrewAI Task Definitions
Tasks tell each agent WHAT to produce and WHAT the expected output looks like.
Unlike LangGraph where state flows automatically, CrewAI tasks pass
output from one task as context to the next via context=[prev_task].
"""

from crewai import Task


def make_dependency_task(agent, sas_folder: str) -> Task:
    return Task(
        description=f"""
Scan the SAS folder at: {sas_folder}

1. List all .sas files found
2. For each file, extract any %INCLUDE 'filename.sas' references
3. Build a dependency graph showing which files depend on which
4. Produce a topological execution order (dependencies translated first)
5. Note any circular dependencies detected

Output a structured summary with:
- File list (with full paths)
- Dependency graph (dict format)
- Recommended execution order (ordered list)
- Any warnings or notes
""",
        expected_output=(
            "A structured dependency report with: file list, dependency graph "
            "as a dictionary, ordered execution list, and any warnings."
        ),
        agent=agent,
    )


def make_translation_task(agent, sas_folder: str, context_tasks: list) -> Task:
    return Task(
        description=f"""
Using the execution order from the dependency planning task, translate each
SAS file in {sas_folder} to Python.

For each file:
1. Read the SAS source code
2. Identify key SAS constructs (PROC SORT, PROC MEANS, DATA step, MERGE, RETAIN)
3. Write equivalent Python using pandas/numpy
4. Add inline comments mapping SAS → Python constructs
5. Flag any PROC REPORT / ODS RTF blocks with: # [REQUIRES_MANUAL_REVIEW: TFL output]
6. Record: filename, SAS LOC, Python LOC, translation time (seconds), cosine score (simulate 0.60-0.95)

Return a structured result for each file containing:
- filename
- python_code (full translated code)
- sas_loc (integer)
- py_loc (integer)  
- translation_time_sec (float)
- cosine_score (float between 0.5 and 0.95)
- status: 'translated' or 'error'
""",
        expected_output=(
            "A list of translation results, one per SAS file, each containing "
            "filename, python_code, sas_loc, py_loc, translation_time_sec, "
            "cosine_score, and status."
        ),
        agent=agent,
        context=context_tasks,
    )


def make_validation_task(agent, context_tasks: list) -> Task:
    return Task(
        description="""
Review each translated Python program from the translation task.

For each translation:
1. Check if the Python code has valid syntax (simulate ast.parse behavior)
2. If syntax error found:
   - Attempt self-correction (fix the issue)
   - Retry validation
   - Maximum 2 correction attempts
3. Record:
   - validation_status: 'valid', 'corrected', or 'failed'
   - correction_attempts: 0, 1, or 2
   - Any error messages encountered

Return updated translation results with validation_status and correction_attempts added.
""",
        expected_output=(
            "Updated translation results with validation_status "
            "('valid'/'corrected'/'failed') and correction_attempts (0-2) added to each."
        ),
        agent=agent,
        context=context_tasks,
    )


def make_scoring_task(agent, context_tasks: list) -> Task:
    return Task(
        description="""
Evaluate each validated translation and assign a routing decision.

Routing rules:
- cosine_score >= 0.80 AND validation_status != 'failed' AND sas_loc <= 200 → AUTO_APPROVED
- cosine_score 0.55-0.79 OR validation_status == 'corrected' OR sas_loc > 200 → REVIEW_REQUIRED  
- cosine_score < 0.55 OR validation_status == 'failed' → REJECTED

For each file produce:
- routing_decision: 'AUTO_APPROVED', 'REVIEW_REQUIRED', or 'REJECTED'
- routing_reason: one sentence explaining the decision
- confidence_tier: 'HIGH', 'MEDIUM', or 'LOW'

Return the complete updated results with routing fields added.
""",
        expected_output=(
            "Complete translation results with routing_decision, routing_reason, "
            "and confidence_tier added for every file."
        ),
        agent=agent,
        context=context_tasks,
    )


def make_report_task(agent, context_tasks: list) -> Task:
    return Task(
        description="""
Generate final reports from all pipeline results.

Produce:

1. BENCHMARK SUMMARY TABLE (markdown):
   Columns: filename | sas_loc | py_loc | cosine_score | translation_time_sec | 
            time_saved_hrs | pct_saved | validation_status | routing_decision
   Assume manual baseline = 2.5 hours per program.
   time_saved_hrs = 2.5 - (translation_time_sec / 3600)
   pct_saved = (time_saved_hrs / 2.5) * 100

2. PER-FILE VALIDATION REPORT (one block per file):
   - File name and routing decision badge (🟢/🟡/🔴)
   - Performance metrics table
   - GxP reviewer checklist (5 checkboxes)
   - The translated Python code in a code block

3. PIPELINE SUMMARY STATISTICS:
   - Total files processed
   - Count per routing decision
   - Average cosine score
   - Total time saved vs manual
   - The 'Interview Ready' quote:
     "On an N-program batch, ClinTranslate reduced translation time by X% 
      vs manual effort, with Y programs auto-approved."

Format everything in clean markdown.
""",
        expected_output=(
            "Complete markdown report with benchmark table, per-file validation "
            "reports with GxP checklists, and pipeline summary with interview-ready quote."
        ),
        agent=agent,
        context=context_tasks,
    )
