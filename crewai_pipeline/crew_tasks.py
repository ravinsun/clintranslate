"""
ClinTranslate v5 — CrewAI Task Definitions
Tasks tell each agent WHAT to produce and WHAT the expected output looks like.
"""

from crewai import Task


def make_dependency_task(agent, sas_folder: str, file_list: str = "") -> Task:
    files_section = f"""
The following SAS files exist in this folder — work ONLY with these exact filenames:
{file_list}

Do NOT invent or assume other filenames. Every output must reference only the files listed above.
""" if file_list else ""

    return Task(
        description=f"""
Scan the SAS folder at: {sas_folder}
{files_section}
1. List all .sas files found (use the list above)
2. For each file, extract any %INCLUDE 'filename.sas' references
3. Build a dependency graph showing which files depend on which
4. Produce a topological execution order (dependencies translated first)
5. Note any circular dependencies detected

Output a structured summary with:
- File list (exact filenames only)
- Dependency graph (dict format)
- Recommended execution order (ordered list)
- Any warnings or notes
""",
        expected_output=(
            "A structured dependency report with: exact file list, dependency graph, "
            "ordered execution list, and any warnings."
        ),
        agent=agent,
    )


def make_translation_task(agent, sas_folder: str, context_tasks: list,
                           file_list: str = "") -> Task:
    files_section = f"""
Translate ONLY these specific files — do not invent other filenames:
{file_list}
""" if file_list else ""

    return Task(
        description=f"""
Using the execution order from the dependency planning task, translate each
SAS file in {sas_folder} to Python.
{files_section}
For each file:
1. Read the SAS source code
2. Identify key SAS constructs (PROC SORT, PROC MEANS, DATA step, MERGE, RETAIN)
3. Write equivalent Python using pandas/numpy
4. Add inline comments mapping SAS → Python constructs
5. Flag any PROC REPORT / ODS RTF blocks with: # [REQUIRES_MANUAL_REVIEW: TFL output]
6. Record: filename, SAS LOC, Python LOC, translation time (seconds), cosine score (0.50-0.95)

IMPORTANT: Use the EXACT filenames from the dependency task. Do not rename files.

Return a structured result for each file containing:
- filename (exact, from the file list)
- python_code (full translated code)
- sas_loc (integer)
- py_loc (integer)
- translation_time_sec (float)
- cosine_score (float — reflect complexity: TFL/complex programs score lower 0.50-0.65)
- status: 'translated' or 'error'
- tfl_flag: true if PROC REPORT or ODS RTF detected
""",
        expected_output=(
            "A list of translation results for each SAS file, each containing "
            "filename, python_code, sas_loc, py_loc, translation_time_sec, "
            "cosine_score, status, and tfl_flag."
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

IMPORTANT: Report realistic outcomes — not all programs will be valid on first attempt.
Programs with PROC REPORT or complex macros are more likely to need correction.

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

Apply these routing rules STRICTLY:
- cosine_score >= 0.80 AND validation_status != 'failed' AND sas_loc <= 200 → AUTO_APPROVED
- cosine_score 0.55-0.79 OR validation_status == 'corrected' OR sas_loc > 200 → REVIEW_REQUIRED
- cosine_score < 0.55 OR validation_status == 'failed' OR tfl_flag == true → REJECTED

For each file produce:
- routing_decision: exactly 'AUTO_APPROVED', 'REVIEW_REQUIRED', or 'REJECTED'
- routing_reason: one sentence explaining the decision with the actual score
- confidence_tier: 'HIGH', 'MEDIUM', or 'LOW'

IMPORTANT: Apply rules strictly. TFL-flagged programs MUST be REJECTED.
Programs with low cosine scores MUST be REJECTED. Do not approve everything.

Return the complete updated results with routing fields added.
""",
        expected_output=(
            "Complete translation results with routing_decision (AUTO_APPROVED/"
            "REVIEW_REQUIRED/REJECTED), routing_reason, and confidence_tier "
            "for every file. Must include a mix of decisions — not all AUTO_APPROVED."
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
   Use routing emojis: 🟢 AUTO_APPROVED, 🟡 REVIEW_REQUIRED, 🔴 REJECTED

2. PER-FILE VALIDATION REPORT (one block per file):
   - File name and routing decision badge (🟢/🟡/🔴)
   - Performance metrics table
   - GxP reviewer checklist (5 checkboxes per 21 CFR Part 11)
   - Note if TFL flagged

3. PIPELINE SUMMARY STATISTICS:
   - Total files, count per routing decision
   - Average cosine score
   - Total time saved vs manual
   - Interview-ready quote:
     "On an N-program batch, ClinTranslate reduced translation time by X%
      vs manual effort, with Y AUTO_APPROVED, Z REVIEW_REQUIRED, W REJECTED."

Format everything in clean markdown.
""",
        expected_output=(
            "Complete markdown report with benchmark table showing all routing decisions "
            "(mix of AUTO/REVIEW/REJECTED), per-file validation reports, "
            "and pipeline summary with interview-ready quote."
        ),
        agent=agent,
        context=context_tasks,
    )
