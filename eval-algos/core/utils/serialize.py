import argparse
import sys
import os
import pandas as pd
import json
import glob
from typing import Optional, Dict, Any

# Add the current directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
eval_algos_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.append(eval_algos_dir)

from .config import SeasonConfig


def clean_json(dataframe: pd.DataFrame) -> str:
    """
    Convert a pandas DataFrame to a clean JSON string with proper formatting.
    """
    json_str = dataframe.to_json(orient='records', indent=2)
    clean_json_str = json_str.replace('\\/', '/')
    return clean_json_str


def load_consolidated_rewards(season: str, measurement_period: str) -> Optional[pd.DataFrame]:
    """Load the consolidated rewards CSV file."""
    config = SeasonConfig(season)
    paths = config.get_measurement_period_paths(measurement_period)
    outputs_dir = paths['outputs']
    
    consolidated_file = os.path.join(outputs_dir, f"{measurement_period}_consolidated_rewards.csv")
    if os.path.exists(consolidated_file):
        return pd.read_csv(consolidated_file)
    else:
        print(f"Warning: Consolidated rewards file not found: {consolidated_file}")
        return None


def load_metrics_data(season: str, measurement_period: str, model_type: str) -> Optional[pd.DataFrame]:
    """Load metrics data for a specific model type."""
    config = SeasonConfig(season)
    paths = config.get_measurement_period_paths(measurement_period)
    data_dir = paths['data']
    
    # Look for metrics files
    if model_type == 'devtooling':
        metrics_file = os.path.join(data_dir, 'devtooling__raw_metrics.json')
    elif model_type == 'onchain':
        # Use the metrics by project file for onchain
        metrics_file = os.path.join(data_dir, 'onchain__metrics_by_project.csv')
    else:
        return None
    
    if os.path.exists(metrics_file):
        if metrics_file.endswith('.json'):
            with open(metrics_file, 'r') as f:
                data = json.load(f)
            return pd.DataFrame(data)
        else:
            return pd.read_csv(metrics_file)
    else:
        print(f"Warning: Metrics file not found: {metrics_file}")
        return None


def serialize_devtooling_results(season: str, measurement_period: str, df_rewards: Optional[pd.DataFrame] = None) -> None:
    """Serialize devtooling results combining metadata, metrics and rewards data."""
    try:
        config = SeasonConfig(season)
        paths = config.get_measurement_period_paths(measurement_period)
        outputs_dir = paths['outputs']
        data_dir = paths['data']
        
        os.makedirs(outputs_dir, exist_ok=True)
        
        # STEP 1: Load project metadata first to get ALL projects with their IDs
        project_metadata_path = os.path.join(data_dir, 'devtooling__project_metadata.csv')
        if not os.path.exists(project_metadata_path):
            raise FileNotFoundError(f"Devtooling project metadata not found: {project_metadata_path}")
        
        project_metadata_df = pd.read_csv(project_metadata_path)
        if project_metadata_df.empty:
            print("No devtooling project metadata found")
            return
        
        # Ensure required columns exist
        required_columns = ['project_name', 'project_id', 'display_name']
        missing_columns = [col for col in required_columns if col not in project_metadata_df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns in devtooling metadata: {missing_columns}")
        
        # STEP 2: Load consolidated rewards if not provided
        if df_rewards is None:
            df_rewards = load_consolidated_rewards(season, measurement_period)
        
        # Create a lookup for rewards by op_atlas_id
        rewards_lookup = {}
        if df_rewards is not None:
            devtooling_mask = df_rewards['filename'].str.contains('devtooling', na=False, case=False)
            devtooling_rewards = df_rewards[devtooling_mask]
            
            if not devtooling_rewards.empty:
                for _, reward_row in devtooling_rewards.iterrows():
                    op_atlas_id = reward_row.get('op_atlas_id')
                    if op_atlas_id:
                        rewards_lookup[op_atlas_id] = {
                            'op_reward': reward_row.get('op_reward', 0)
                        }
        
        # STEP 3: Load devtooling metrics
        metrics_df = load_metrics_data(season, measurement_period, 'devtooling')
        
        # Create a lookup for metrics by op_atlas_id
        metrics_lookup = {}
        if metrics_df is not None:
            for _, metrics_row in metrics_df.iterrows():
                op_atlas_id = metrics_row.get('project_name')  # This is op_atlas_id
                if op_atlas_id:
                    metrics_lookup[op_atlas_id] = metrics_row.to_dict()
        
        # STEP 4: Create the final JSON structure - include ALL projects from metadata
        results = []
        for _, metadata_row in project_metadata_df.iterrows():
            op_atlas_id = metadata_row.get('project_name')  # This is op_atlas_id
            oso_project_id = metadata_row.get('project_id')
            display_name = metadata_row.get('display_name', '')
            
            # Ensure we have both IDs
            if not op_atlas_id or not oso_project_id:
                print(f"Warning: Missing IDs for project - op_atlas_id: {op_atlas_id}, oso_project_id: {oso_project_id}")
                continue
            
            # Get reward data if available, otherwise use defaults
            reward_data = rewards_lookup.get(op_atlas_id, {
                'op_reward': 0
            })
            
            # Get eligibility from metadata
            is_eligible = metadata_row.get('is_eligible', True)
            
            # Get metrics data if available
            metrics_data = metrics_lookup.get(op_atlas_id, {})
            
            result = {
                'op_atlas_id': op_atlas_id,
                'oso_project_id': oso_project_id,
                'display_name': display_name,
                'is_eligible': is_eligible,
                'op_reward': reward_data['op_reward'],
                'round_id': str(season)
            }
            
            # Add all metrics data (excluding redundant fields)
            for col, value in metrics_data.items():
                if col not in result and col not in ['project_name', 'project_id']:
                    result[col] = value
            
            results.append(result)
        
        # Save to JSON file
        output_file = os.path.join(outputs_dir, 'devtooling__results.json')
        # Convert results to DataFrame for clean JSON formatting
        results_df = pd.DataFrame(results)
        clean_json_str = clean_json(results_df)
        with open(output_file, 'w') as f:
            f.write(clean_json_str)
        
        print(f"✓ Devtooling results serialized to {output_file} ({len(results)} projects)")
        
    except Exception as e:
        print(f"Error in serialize_devtooling_results: {str(e)}")
        raise


def serialize_onchain_results(season: str, measurement_period: str, df_rewards: Optional[pd.DataFrame] = None) -> None:
    """Serialize onchain results combining metadata, metrics and rewards data."""
    config = SeasonConfig(season)
    paths = config.get_measurement_period_paths(measurement_period)
    outputs_dir = paths['outputs']
    data_dir = paths['data']
    
    os.makedirs(outputs_dir, exist_ok=True)
    
    # STEP 1: Load project metadata first to get ALL projects with their IDs
    project_metadata_path = os.path.join(data_dir, 'onchain__project_metadata.csv')
    if not os.path.exists(project_metadata_path):
        raise FileNotFoundError(f"Onchain project metadata not found: {project_metadata_path}")
    
    project_metadata_df = pd.read_csv(project_metadata_path)
    if project_metadata_df.empty:
        print("No onchain project metadata found")
        return
    
    # Ensure required columns exist
    required_columns = ['project_name', 'project_id', 'display_name']
    missing_columns = [col for col in required_columns if col not in project_metadata_df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns in onchain metadata: {missing_columns}")
    
    # STEP 2: Load consolidated rewards if not provided
    if df_rewards is None:
        df_rewards = load_consolidated_rewards(season, measurement_period)
    
    # Create a lookup for rewards by op_atlas_id
    rewards_lookup = {}
    if df_rewards is not None:
        onchain_mask = df_rewards['filename'].str.contains('onchain', na=False, case=False)
        onchain_rewards = df_rewards[onchain_mask]
        
        if not onchain_rewards.empty:
            for _, reward_row in onchain_rewards.iterrows():
                op_atlas_id = reward_row.get('op_atlas_id')
                if op_atlas_id:
                    rewards_lookup[op_atlas_id] = {
                        'op_reward': reward_row.get('op_reward', 0)
                    }
    
    # STEP 3: Load and process onchain metrics
    metrics_df = load_metrics_data(season, measurement_period, 'onchain')
    
    # Process onchain metrics to create nested structure
    processed_metrics = {}
    if metrics_df is not None:
        try:
            # Group metrics by project and create nested structure
            # Filter to only most recent measurement period
            current_period = metrics_df['sample_date'].max()
            filtered_metrics = metrics_df[metrics_df['sample_date'] == current_period]
            
            for _, row in filtered_metrics.iterrows():
                project_name = row['project_name']  # This is op_atlas_id
                if project_name not in processed_metrics:
                    processed_metrics[project_name] = {
                        'project_id': row['project_id'],
                        'display_name': row['display_name'],
                        'eligibility_metrics': {},
                        'monthly_metrics': {
                            'defillama_tvl': 0
                        }
                    }
                
                # Add to monthly_metrics with S8-specific mapping and sum aggregation
                metric_name = row['metric_name']
                amount = row['amount']
                if pd.notna(amount):
                    # Map S8 metric names to S7 format
                    if metric_name == 'layer2_gas_fees_amortized':
                        target_metric = 'gas_fees'
                    elif metric_name in ['farcaster_users', 'layer2_gas_fees']:
                        # Skip these metrics for S8
                        continue
                    elif metric_name == 'worldchain_users_aggregation':
                        # Combine worldchain_users_aggregation with active_addresses_aggregation
                        target_metric = 'active_addresses_aggregation'
                    else:
                        target_metric = metric_name
                    
                    # Sum the metric values
                    if target_metric in processed_metrics[project_name]['monthly_metrics']:
                        processed_metrics[project_name]['monthly_metrics'][target_metric] += amount
                    else:
                        processed_metrics[project_name]['monthly_metrics'][target_metric] = amount
        except Exception as e:
            print(f"Error processing onchain metrics: {e}")
    
    # Add eligibility metrics from project metadata to processed_metrics
    for _, row in project_metadata_df.iterrows():
        project_name = row['project_name']  # This is op_atlas_id
        if project_name not in processed_metrics:
            processed_metrics[project_name] = {
                'project_id': row['project_id'],
                'display_name': row['display_name'],
                'eligibility_metrics': {},
                'monthly_metrics': {'defillama_tvl': 0}
            }
        
        # Add eligibility metrics
        if 'transaction_count' in row and pd.notna(row['transaction_count']):
            processed_metrics[project_name]['eligibility_metrics']['transaction_count'] = row['transaction_count']
        if 'active_days' in row and pd.notna(row['active_days']):
            processed_metrics[project_name]['eligibility_metrics']['active_days'] = row['active_days']
    
    # STEP 4: Create the final JSON structure - include ALL projects from metadata
    results = []
    for _, metadata_row in project_metadata_df.iterrows():
        op_atlas_id = metadata_row.get('project_name')  # This is op_atlas_id
        oso_project_id = metadata_row.get('project_id')
        display_name = metadata_row.get('display_name', '')
        
        # Ensure we have both IDs
        if not op_atlas_id or not oso_project_id:
            print(f"Warning: Missing IDs for project - op_atlas_id: {op_atlas_id}, oso_project_id: {oso_project_id}")
            continue
        
        # Get reward data if available, otherwise use defaults
        reward_data = rewards_lookup.get(op_atlas_id, {
            'op_reward': 0
        })
        
        # Get eligibility from metadata
        is_eligible = metadata_row.get('is_eligible', True)
        
        # Get processed metrics data if available
        metrics_data = processed_metrics.get(op_atlas_id, {
            'eligibility_metrics': {},
            'monthly_metrics': {'defillama_tvl': 0}
        })
        
        result = {
            'oso_project_id': oso_project_id,
            'op_atlas_id': op_atlas_id,
            'display_name': display_name,
            'is_eligible': is_eligible,
            'op_reward': reward_data['op_reward'],
            'round_id': str(season),
            'eligibility_metrics': metrics_data['eligibility_metrics'],
            'monthly_metrics': metrics_data['monthly_metrics']
        }
        
        # Ensure defillama_tvl is always present (set to null if not found or zero)
        if 'monthly_metrics' in result and isinstance(result['monthly_metrics'], dict):
            if 'defillama_tvl' not in result['monthly_metrics']:
                result['monthly_metrics']['defillama_tvl'] = None
            elif result['monthly_metrics']['defillama_tvl'] == 0:
                result['monthly_metrics']['defillama_tvl'] = None
        else:
            # If no monthly_metrics at all, create it with defillama_tvl
            result['monthly_metrics'] = {'defillama_tvl': None}
        
        results.append(result)
    
    # Save to JSON file
    output_file = os.path.join(outputs_dir, 'onchain__results.json')
    # Convert results to DataFrame for clean JSON formatting
    results_df = pd.DataFrame(results)
    clean_json_str = clean_json(results_df)
    with open(output_file, 'w') as f:
        f.write(clean_json_str)
    
    print(f"✓ Onchain results serialized to {output_file} ({len(results)} projects)")


def serialize_results(season: str, measurement_period: str) -> None:
    """Serialize all results for a specific season and measurement period."""
    print(f"Serializing devtooling results for S{season} - {measurement_period}...")
    serialize_devtooling_results(season, measurement_period)
    
    print(f"Serializing onchain results for S{season} - {measurement_period}...")
    serialize_onchain_results(season, measurement_period)
    
    print(f"✓ All results serialized for S{season} - {measurement_period}")


def main():
    """Main entry point for the unified serialization script."""
    parser = argparse.ArgumentParser(description='Serialize results for a specific season and measurement period')
    parser.add_argument('--season', '-s', type=str, required=True, choices=['7', '8'],
                       help='Season number (7 or 8)')
    parser.add_argument('--period', '-p', type=str, required=True,
                       help='Measurement period (e.g., M1, M2)')
    
    args = parser.parse_args()
    
    try:
        serialize_results(args.season, args.period)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
