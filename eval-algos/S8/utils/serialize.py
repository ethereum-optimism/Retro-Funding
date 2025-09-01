#!/usr/bin/env python3

import os
import sys
import pandas as pd
from typing import Optional
import argparse


script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../..'))
eval_algos_dir = os.path.abspath(os.path.join(script_dir, '../..'))
sys.path.extend([project_root, eval_algos_dir])

from S8.utils.config import get_measurement_period_paths
from S8.utils.consolidate_rewards import consolidate_rewards, save_consolidated_rewards


def clean_json(dataframe: pd.DataFrame) -> str:
    """
    Convert a pandas DataFrame to a clean JSON string with proper formatting.
    
    Args:
        dataframe: The pandas DataFrame to convert to JSON
        
    Returns:
        A clean JSON string with proper formatting and escaped forward slashes
    """
    json_str = dataframe.to_json(orient='records', indent=2)
    clean_json_str = json_str.replace('\\/', '/')
    return clean_json_str


def serialize_devtooling_results(measurement_period: str, df_rewards: Optional[pd.DataFrame] = None) -> None:
    """
    Serialize devtooling metrics and rewards data into a single JSON file.
    
    Args:
        measurement_period: The measurement period (e.g., 'M1', 'M2')
        df_rewards: Optional DataFrame containing consolidated rewards data
    """
    paths = get_measurement_period_paths(measurement_period)
    data_dir = paths['data']
    outputs_dir = paths['outputs']
    
    os.makedirs(outputs_dir, exist_ok=True)
    
    devtooling_metrics_path = os.path.join(data_dir, "devtooling__raw_metrics.json")
    df_metrics = pd.read_json(devtooling_metrics_path)

    try:
        downstream_gas_path = os.path.join(data_dir, "devtooling__downstream_gas_temp.csv")
        
        if os.path.exists(downstream_gas_path):
            df_downstream_gas = pd.read_csv(downstream_gas_path)
            df_metrics['downstream_gas'] = 0.0
            
            for idx, row in df_metrics.iterrows():
                if 'onchain_builder_oso_project_ids' in row and isinstance(row['onchain_builder_oso_project_ids'], list):
                    matching_projects = df_downstream_gas[df_downstream_gas['builder_id'].isin(row['onchain_builder_oso_project_ids'])]
                    if not matching_projects.empty:
                        df_metrics.at[idx, 'downstream_gas'] = matching_projects['gas_fees'].sum()
        else:
            print("Warning: Downstream gas data file not found, downstream_gas will be set to 0")
    except Exception as e:
        print(f"Error calculating downstream gas: {e}")
        print("Setting downstream_gas to 0")
        df_metrics['downstream_gas'] = 0.0

    if 'project_id' in df_metrics.columns:
        df_metrics = df_metrics.rename(columns={'project_id': 'oso_project_id'})
    if 'project_name' in df_metrics.columns:
        df_metrics = df_metrics.rename(columns={'project_name': 'op_atlas_id'})

    df_merged = df_metrics.copy()
    df_merged['op_reward'] = None
    df_merged['round_id'] = '7'

    if df_rewards is not None and not df_rewards.empty:
        df_devtooling_rewards = df_rewards[df_rewards['round_id'] == '7']
        if not df_devtooling_rewards.empty:
            df_merged = df_metrics.merge(
                df_devtooling_rewards[['op_atlas_id', 'op_reward', 'round_id']],
                on='op_atlas_id',
                how='outer'
            )
    df_merged['round_id'] = '7'

    clean_json_str = clean_json(df_merged)
    output_path = os.path.join(outputs_dir, "devtooling__results.json")
    with open(output_path, 'w') as file:
        file.write(clean_json_str)
    
    print(f"✓ Saved devtooling results to {output_path}")


def serialize_onchain_results(measurement_period: str, df_rewards: Optional[pd.DataFrame] = None) -> None:
    """
    Serialize onchain metrics and rewards data into a single JSON file.
    
    Args:
        measurement_period: The measurement period (e.g., 'M1', 'M2')
        df_rewards: Optional DataFrame containing consolidated rewards data
    """
    paths = get_measurement_period_paths(measurement_period)
    data_dir = paths['data']
    outputs_dir = paths['outputs']
    
    os.makedirs(outputs_dir, exist_ok=True)
    
    onchain_metadata_path = os.path.join(data_dir, "onchain__project_metadata.csv")
    df_metrics = pd.read_csv(onchain_metadata_path)
    if 'project_id' in df_metrics.columns:
        df_metrics = df_metrics.rename(columns={'project_id': 'oso_project_id'})
    if 'project_name' in df_metrics.columns:
        df_metrics = df_metrics.rename(columns={'project_name': 'op_atlas_id'})
    
    df_merged = df_metrics.copy()
    df_merged['op_reward'] = None
    df_merged['round_id'] = '8'
    
    if df_rewards is not None and not df_rewards.empty:
        df_onchain_rewards = df_rewards[df_rewards['round_id'] == '8']
        if not df_onchain_rewards.empty:
            df_merged = df_metrics.merge(
                df_onchain_rewards[['op_atlas_id', 'op_reward', 'round_id']],
                on='op_atlas_id',            
                how='outer'
            )
            if 'op_atlas_id_y' in df_merged.columns:
                df_merged = df_merged.drop(columns=['op_atlas_id_y'])
                df_merged = df_merged.rename(columns={'op_atlas_id_x': 'op_atlas_id'})
    
    df_merged['is_eligible'] = df_merged['is_eligible'].fillna(False)
    df_merged['round_id'] = '8'
    
    try:
        df_snapshot_metrics = pd.read_csv(os.path.join(data_dir, "onchain__summary_metric_snapshot.csv"))
        df_snapshot_metrics = df_snapshot_metrics.pivot_table(
            index='op_atlas_id',
            columns='metric_name', 
            values='amount',
            aggfunc='sum'
        ).reset_index()
        df_merged = df_merged.merge(df_snapshot_metrics, on='op_atlas_id', how='left')

        df_merged['eligibility_metrics'] = None
        df_merged['monthly_metrics'] = None
        
        all_monthly_metrics = set()
        for col in df_merged.columns:
            if isinstance(col, str) and '__' in col and any(month in col.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                base_metric = col.split('__')[0]
                all_monthly_metrics.add(base_metric)
        
        for idx, row in df_merged.iterrows():
            monthly_dict = {}
            for metric in all_monthly_metrics:
                monthly_dict[metric] = None
            
            for col in row.index:
                if isinstance(col, str) and '__' in col and any(month in col.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                    if pd.notna(row[col]):
                        base_metric = col.split('__')[0]
                        monthly_dict[base_metric] = row[col]
            
            eligibility_metrics = ['active_days', 'gas_fees', 'transaction_count', 'active_addresses_count', 'contract_invocations']
            eligibility_dict = {}
            for metric in eligibility_metrics:
                if metric in row and pd.notna(row[metric]):
                    eligibility_dict[metric] = row[metric]
            
            df_merged.at[idx, 'eligibility_metrics'] = eligibility_dict
            df_merged.at[idx, 'monthly_metrics'] = monthly_dict
            
            for col in row.index:
                if isinstance(col, str) and (('__' in col and any(month in col.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])) or col in eligibility_metrics):
                    if col in df_merged.columns:
                        df_merged = df_merged.drop(columns=[col])

    except FileNotFoundError:
        print("No snapshot metrics found, will serialize with null metrics")

    clean_json_str = clean_json(df_merged)
    output_path = os.path.join(outputs_dir, "onchain__results.json")
    with open(output_path, 'w') as file:
        file.write(clean_json_str)
    
    print(f"✓ Saved onchain results to {output_path}")


def main():
    """
    Main entry point for the serialization script.
    """
    parser = argparse.ArgumentParser(description='Serialize metrics and rewards data for a specific measurement period')
    parser.add_argument('--measurement-period', '-m', type=str, required=True,
                       help='Measurement period (e.g., M1, M2)')
    
    args = parser.parse_args()
    
    df_rewards = None
    try:
        df_rewards = consolidate_rewards(args.measurement_period)
        if not df_rewards.empty:
            save_consolidated_rewards(df_rewards, args.measurement_period)
        else:
            print("No rewards data found, will serialize with null rewards")
    except Exception as e:
        print(f"Error consolidating rewards: {e}")
        print("Will serialize with null rewards")
    
    serialize_devtooling_results(args.measurement_period, df_rewards)
    serialize_onchain_results(args.measurement_period, df_rewards)


if __name__ == "__main__":
    main()
