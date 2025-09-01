import pandas as pd
from dataclasses import dataclass


@dataclass
class AllocationConfig:
    budget: float
    min_amount_per_project: float
    max_share_per_project: float


def allocate_funding_iterative(scores: pd.Series, funding_balance: float, max_alloc: float) -> pd.Series:
    """
    Iteratively allocates funding based on provided score weights,
    capping each project's allocation to max_alloc.
    """
    score_balance = scores.sum()
    allocations = pd.Series(dtype=float)
    
    # Process projects in descending order of their (initial) allocation scores
    for project, score in scores.sort_values(ascending=False).items():
        if score_balance == 0:
            allocations[project] = 0
        else:
            uncapped_alloc = score / score_balance * funding_balance
            capped_alloc = min(uncapped_alloc, max_alloc)
            allocations[project] = capped_alloc
            funding_balance -= capped_alloc
            score_balance -= score
    return allocations    


def allocate_with_constraints(
    project_scores: pd.Series,
    config: AllocationConfig,
    print_results: bool = True,
    rounding: int = 2,
) -> pd.Series:
    """
    Allocates the budget to projects based on their scores while enforcing:
      1. A maximum cap (max_share_per_project * budget) using an iterative allocation,
      2. Zeroing out projects with allocations below the minimum threshold, and
      3. Reallocating the remaining funds to projects that have not reached the cap.
    
    Args:
        project_scores: Series with project names as index and normalized scores as values
                        (i.e. the weights should sum to 1.0).
        config: AllocationConfig containing the budget and constraint parameters.
        print_results: Whether to print the results.
        rounding: Number of decimal places for rounding the final allocations.
        
    Returns:
        Series with the final funding allocation per project.
    """
    # Calculate the maximum allocation allowed per project
    max_per_project = config.max_share_per_project * config.budget
    
    # Step 1: Compute the initial allocations.
    initial_allocations = project_scores * config.budget
    
    # Apply the iterative allocation to enforce the max cap
    allocations = allocate_funding_iterative(initial_allocations, config.budget, max_per_project)
    
    # Zero out projects that do not reach the minimum funding threshold
    allocations[allocations < config.min_amount_per_project] = 0
    
    # Reallocate remaining funding among projects below the max cap
    max_cap_funding = allocations[allocations == max_per_project].sum()
    remaining_funding = config.budget - max_cap_funding
    remaining_projects = allocations[allocations < max_per_project]
    
    if not remaining_projects.empty:
        additional_alloc = allocate_funding_iterative(remaining_projects, remaining_funding, max_per_project)
        allocations.update(additional_alloc)
    
    allocations = allocations.round(rounding)
    
    return allocations