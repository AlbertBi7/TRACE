"""
TRACE — Analysis Router (Milestones 8)
Disruption simulator + articulation points over the case subgraph.
Deterministic networkx topology; neutral, structural language throughout.
"""

from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user, require_case_access
from app.graph.analysis import load_case_subgraph, analyze
from app.graph.heuristics import compute_heuristic_links
from app.graph.priority import compute_priority_scores

router = APIRouter(prefix="/api/cases", tags=["analysis"])


@router.get("/{case_id}/heuristic-links")
async def heuristic_links(case_id: str, current_user: dict = Depends(get_current_user)):
    """Unconfirmed structural leads (dashed edges in the explorer). Never auto-promoted."""
    await require_case_access(case_id, current_user)
    return await compute_heuristic_links(case_id)


@router.get("/{case_id}/priority-scores")
async def priority_scores(case_id: str, current_user: dict = Depends(get_current_user)):
    """Composite structural prioritization (0-100) with explanations. Not a risk/guilt measure."""
    await require_case_access(case_id, current_user)
    return await compute_priority_scores(case_id)


@router.get("/{case_id}/analysis/structure")
async def structure(case_id: str, current_user: dict = Depends(get_current_user)):
    """Static structure: articulation points + component summary (no removal)."""
    await require_case_access(case_id, current_user)
    nodes, edges = await load_case_subgraph(case_id)
    return analyze(nodes, edges)


@router.post("/{case_id}/analysis/simulate-removal/{entity_id}")
async def simulate_removal(
    case_id: str,
    entity_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Before/after connectivity metrics when one node is hypothetically removed."""
    await require_case_access(case_id, current_user)
    nodes, edges = await load_case_subgraph(case_id)
    return analyze(nodes, edges, remove_id=entity_id)
