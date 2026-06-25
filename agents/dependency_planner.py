"""
Agent 1: Dependency Planner
Scans a folder of SAS files, resolves %INCLUDE and macro dependencies,
and returns an ordered execution plan (topological sort).
"""

import os
import re
from pathlib import Path
from typing import TypedDict, List, Dict
from collections import defaultdict, deque


class PlannerState(TypedDict):
    sas_folder: str
    sas_files: List[str]
    dependency_graph: Dict[str, List[str]]
    execution_order: List[str]
    planner_notes: List[str]


def scan_sas_files(folder: str) -> List[str]:
    """Find all .sas files in the given folder."""
    p = Path(folder)
    return sorted([str(f) for f in p.glob("*.sas")])


def extract_dependencies(filepath: str) -> List[str]:
    """
    Extract %INCLUDE references and macro invocations from a SAS file.
    Returns list of dependency filenames (basenames only).
    """
    deps = []
    try:
        with open(filepath, "r", errors="ignore") as f:
            content = f.read()

        # Match %include 'filename.sas'; or %include "filename.sas";
        include_pattern = re.findall(
            r'%include\s+["\']([^"\']+\.sas)["\']', content, re.IGNORECASE
        )
        deps.extend([Path(p).name for p in include_pattern])

        # Match %macro_name() calls that correspond to known files
        # (we resolve these after scanning all files)
        macro_calls = re.findall(r'%(\w+)\s*\(', content, re.IGNORECASE)
        deps.extend(macro_calls)

    except Exception as e:
        pass

    return list(set(deps))


def build_dependency_graph(sas_files: List[str]) -> Dict[str, List[str]]:
    """Build adjacency list: file -> [files it depends on]."""
    file_map = {Path(f).name: f for f in sas_files}
    graph = {}

    for filepath in sas_files:
        name = Path(filepath).name
        raw_deps = extract_dependencies(filepath)
        # Only keep deps that exist in our folder
        resolved_deps = [d for d in raw_deps if d in file_map]
        graph[name] = resolved_deps

    return graph


def topological_sort(graph: Dict[str, List[str]]) -> List[str]:
    """
    Kahn's algorithm for topological sort.
    Returns execution order (dependencies first).
    """
    in_degree = defaultdict(int)
    all_nodes = set(graph.keys())

    for node, deps in graph.items():
        for dep in deps:
            in_degree[node] += 1
            all_nodes.add(dep)

    # Nodes with no dependencies go first
    queue = deque([n for n in all_nodes if in_degree[n] == 0])
    order = []

    while queue:
        node = queue.popleft()
        order.append(node)
        # For nodes that depend on this one, reduce their in_degree
        for dependent, deps in graph.items():
            if node in deps:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

    # If cycle detected, fall back to alphabetical order
    if len(order) < len(all_nodes):
        remaining = [n for n in all_nodes if n not in order]
        order.extend(remaining)

    return order


def run_dependency_planner(state: PlannerState) -> PlannerState:
    """
    LangGraph node: Scans folder, builds dependency graph, returns execution order.
    """
    notes = []
    folder = state["sas_folder"]

    sas_files = scan_sas_files(folder)
    notes.append(f"Found {len(sas_files)} SAS file(s) in {folder}")

    if not sas_files:
        state["sas_files"] = []
        state["dependency_graph"] = {}
        state["execution_order"] = []
        state["planner_notes"] = notes
        return state

    graph = build_dependency_graph(sas_files)
    order = topological_sort(graph)

    # Map back to full paths, preserving order
    file_map = {Path(f).name: f for f in sas_files}
    ordered_paths = [file_map[name] for name in order if name in file_map]

    notes.append(f"Execution order: {[Path(p).name for p in ordered_paths]}")
    deps_found = {k: v for k, v in graph.items() if v}
    if deps_found:
        notes.append(f"Dependencies detected: {deps_found}")
    else:
        notes.append("No %INCLUDE dependencies detected — files are independent")

    state["sas_files"] = ordered_paths
    state["dependency_graph"] = graph
    state["execution_order"] = [Path(p).name for p in ordered_paths]
    state["planner_notes"] = notes

    return state
