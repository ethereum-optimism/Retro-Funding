import argparse
import sys
import os
import importlib.util
import yaml
import pandas as pd
from pathlib import Path

# Add the current directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
eval_algos_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.append(eval_algos_dir)

from .config import get_model_yaml_path, get_output_path, ensure_directories
from ..models.allocator import allocate_with_constraints, AllocationConfig


# Define score column mappings for each model type
MODEL_SCORE_COLUMNS = {
    'devtooling': 'v_aggregated',
    'onchain': 'weighted_score'
}


def find_yaml_file(season: str, measurement_period: str, model_name: str) -> str:
    """
    Find the exact YAML file for a model, with or without .yaml extension.
    Raises FileNotFoundError if the file doesn't exist.
    """
    # Get the base path using the convenience function
    base_path = get_model_yaml_path(season, measurement_period, model_name)
    
    # Try with .yaml extension first
    yaml_path = f"{base_path}.yaml"
    if os.path.exists(yaml_path):
        return yaml_path
    
    # Try without extension
    if os.path.exists(base_path):
        return base_path
    
    # If neither exists, raise error
    raise FileNotFoundError(f"YAML file not found: {model_name} or {model_name}.yaml")


def load_allocation_config(yaml_path: str) -> AllocationConfig:
    """
    Load allocation configuration from YAML file.
    Raises ValueError if allocation config is missing or invalid.
    """
    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)
    
    allocation_config = config.get('allocation')
    if not allocation_config:
        raise ValueError(f"No allocation configuration found in {yaml_path}")
    
    required_fields = ['budget', 'min_amount_per_project', 'max_share_per_project']
    missing_fields = [field for field in required_fields if field not in allocation_config]
    
    if missing_fields:
        raise ValueError(f"Missing required allocation fields in {yaml_path}: {missing_fields}")
    
    return AllocationConfig(
        budget=allocation_config['budget'],
        min_amount_per_project=allocation_config['min_amount_per_project'],
        max_share_per_project=allocation_config['max_share_per_project']
    )


def allocate_rewards(results: pd.DataFrame, yaml_path: str) -> pd.DataFrame:
    """
    Allocate rewards using the allocation configuration from the YAML file.
    Returns DataFrame with project_id, project_name, display_name, score, and allocated_amount.
    """
    # Load allocation configuration
    allocation_config = load_allocation_config(yaml_path)
    
    # Create score series for allocation
    score_series = results.set_index('project_id')['score']
    
    # Run allocation
    allocations = allocate_with_constraints(
        project_scores=score_series,
        config=allocation_config,
        print_results=False
    )
    
    # Create final results DataFrame
    final_results = results.copy()
    final_results['allocated_amount'] = final_results['project_id'].map(allocations)
    
    # Filter to only projects that received funding
    funded_results = final_results[final_results['allocated_amount'] > 0].copy()
    
    if funded_results.empty:
        raise ValueError("No projects received funding after allocation")
    
    return funded_results


def save_rewards_csv(results: pd.DataFrame, season: str, measurement_period: str, model_name: str) -> str:
    """Save rewards to CSV file and return the file path"""
    output_path = get_output_path(season, measurement_period, model_name)
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Save to CSV
    results.to_csv(output_path, index=False)
    
    print(f"✓ Rewards saved to {output_path}")
    return output_path


def process_devtooling(season: str, measurement_period: str, model_name: str) -> None:
    """Complete devtooling model workflow: execute, extract results, allocate, and save"""
    print(f"Processing devtooling model: {model_name}")
    
    # Find YAML file
    yaml_path = find_yaml_file(season, measurement_period, model_name)
    
    # Import and execute devtooling model
    shared_model_path = os.path.join(eval_algos_dir, 'core', 'models', 'devtooling.py')
    spec = importlib.util.spec_from_file_location("devtooling_module", shared_model_path)
    devtooling_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(devtooling_module)
    
    # Run simulation
    analysis = devtooling_module.run_simulation(yaml_path)
    
    # Extract and standardize results
    results = analysis.get('devtooling_project_results')
    if results is None:
        raise ValueError("No devtooling_project_results found in analysis")
    
    score_column = MODEL_SCORE_COLUMNS['devtooling']
    if score_column not in results.columns:
        raise ValueError(f"Score column '{score_column}' not found in devtooling results")
    
    # Filter to only eligible projects with positive scores
    eligible_results = results[
        (results['is_eligible'] == 1) & 
        (results[score_column] > 0)
    ].copy()
    
    if eligible_results.empty:
        raise ValueError("No eligible projects with positive scores found")
    
    # Select and rename columns
    final_results = eligible_results[[
        'project_id', 'project_name', 'display_name', score_column
    ]].copy()
    final_results.rename(columns={score_column: 'score'}, inplace=True)
    
    # Normalize scores to sum to 1.0
    total_score = final_results['score'].sum()
    if total_score > 0:
        final_results['score'] = final_results['score'] / total_score
    
    print(f"✓ Devtooling model executed for {model_name}")
    print(f"  - {len(final_results)} eligible projects found")
    
    # Allocate rewards
    print(f"Allocating rewards for {model_name}...")
    allocated_results = allocate_rewards(final_results, yaml_path)
    
    # Save results
    save_rewards_csv(allocated_results, season, measurement_period, model_name)
    
    print(f"✓ Successfully processed {model_name}")
    print(f"  - {len(allocated_results)} projects funded")
    print(f"  - Total allocated: ${allocated_results['allocated_amount'].sum():,.2f}")


def process_onchain(season: str, measurement_period: str, model_name: str) -> None:
    """Complete onchain model workflow: execute, extract results, allocate, and save"""
    print(f"Processing onchain model: {model_name}")
    
    # Find YAML file
    yaml_path = find_yaml_file(season, measurement_period, model_name)
    
    # Import and execute onchain model
    shared_model_path = os.path.join(eval_algos_dir, 'core', 'models', 'onchain_builders.py')
    spec = importlib.util.spec_from_file_location("onchain_module", shared_model_path)
    onchain_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(onchain_module)
    
    # Run simulation
    analysis = onchain_module.run_simulation(yaml_path)
    
    # Extract and standardize results
    results = analysis.get('final_results')
    if results is None:
        raise ValueError("No final_results found in analysis")
    
    score_column = MODEL_SCORE_COLUMNS['onchain']
    if score_column not in results.columns:
        raise ValueError(f"Score column '{score_column}' not found in onchain results")
    
    # Filter to only projects with positive scores
    eligible_results = results[results[score_column] > 0].copy()
    
    if eligible_results.empty:
        raise ValueError("No projects with positive scores found")
    
    # Select and rename columns
    final_results = eligible_results[[
        'project_id', 'project_name', 'display_name', score_column
    ]].copy()
    final_results.rename(columns={score_column: 'score'}, inplace=True)
    
    # Normalize scores to sum to 1.0
    total_score = final_results['score'].sum()
    if total_score > 0:
        final_results['score'] = final_results['score'] / total_score
    
    print(f"✓ Onchain model executed for {model_name}")
    print(f"  - {len(final_results)} eligible projects found")
    
    # Allocate rewards
    print(f"Allocating rewards for {model_name}...")
    allocated_results = allocate_rewards(final_results, yaml_path)
    
    # Save results
    save_rewards_csv(allocated_results, season, measurement_period, model_name)
    
    print(f"✓ Successfully processed {model_name}")
    print(f"  - {len(allocated_results)} projects funded")
    print(f"  - Total allocated: ${allocated_results['allocated_amount'].sum():,.2f}")


def main():
    """Main entry point for the model processing script"""
    parser = argparse.ArgumentParser(description='Process models and calculate rewards for any season')
    parser.add_argument('--algo', '-a', type=str, required=True, choices=['devtooling', 'onchain'],
                       help='Algorithm type to process (devtooling or onchain)')
    parser.add_argument('--weights', '-w', type=str, required=True,
                       help='Name of the weights file to use (e.g., arcturus, goldilocks)')
    parser.add_argument('--season', '-s', type=str, required=True, choices=['7', '8'],
                       help='Season number (7 or 8)')
    parser.add_argument('--period', '-p', type=str, required=True,
                       help='Measurement period (e.g., M1, M2)')
    
    args = parser.parse_args()
    
    # Ensure directories exist
    ensure_directories(args.season, args.period)
    
    try:
        if args.algo == 'devtooling':
            process_devtooling(args.season, args.period, args.weights)
        elif args.algo == 'onchain':
            process_onchain(args.season, args.period, args.weights)
        
        print(f"\n✓ Model processed successfully for S{args.season} - {args.period}")
    except Exception as e:
        print(f"\nError: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
