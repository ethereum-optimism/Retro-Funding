import pandas as pd
import yaml
import json
import os

# Define directory path
directory_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


# Load YAML configuration
yaml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'weight', 'heuristics.yaml')
with open(yaml_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)


# Extract weights, thresholds, and file names
weights = config['model']['parameters']['weights']
thresholds = config['model']['parameters']['thresholds']
projects_file = config['data']['projects_file']
contributor_file = config['data']['contributor_file']
dependency_file = config['data']['dependency_file']

# Construct file paths
projects_path = os.path.join(directory_path, projects_file)
contributor_path = os.path.join(directory_path, contributor_file)
dependency_path = os.path.join(directory_path, dependency_file)

# Load data
projects_df = pd.read_csv(projects_path)
with open(contributor_path, 'r', encoding='utf-8') as file:
    contributor_data = json.load(file)
contributor_df = pd.DataFrame(contributor_data)
dependency_df = pd.read_csv(dependency_path)

# Compute dependency metrics
event_count = dependency_df.groupby('project_id').size().reset_index(name='dependents')
commit_volume = dependency_df[dependency_df['event_type'] == 'COMMIT_CODE'].groupby('project_id').size().reset_index(name='commit_volume')
pull_requests = dependency_df[dependency_df['event_type'] == 'PULL_REQUEST_OPENED'].groupby('project_id').size().reset_index(name='pull_requests')
forks_events = dependency_df[dependency_df['event_type'] == 'FORKED'].groupby('project_id').size().reset_index(name='fork_events')
unique_committers = dependency_df[dependency_df['event_type'] == 'COMMIT_CODE'].groupby('project_id')['developer_id'].nunique().reset_index(name='unique_committers')

# Merge dependency metrics
dependency_metrics = event_count.merge(commit_volume, on='project_id', how='outer') \
                                .merge(pull_requests, on='project_id', how='outer') \
                                .merge(forks_events, on='project_id', how='outer') \
                                .merge(unique_committers, on='project_id', how='outer') \
                                .fillna(0)

# Merge all data
merged_df = projects_df[['project_id', 'display_name', 'star_count', 'fork_count']].merge(
    contributor_df[['project_id', 'developer_connection_count']],
    on='project_id',
    how='left'
).merge(
    dependency_metrics,
    on='project_id',
    how='left'
).fillna(0)

# Compute derived metrics
if 'forks_to_import_ratio' in weights:
    merged_df['forks_to_import_ratio'] = merged_df['fork_events'] / (merged_df['unique_committers'] + 1)

# Rename columns
merged_df = merged_df.rename(columns={
    'star_count': 'stars',
    'fork_count': 'forks',
    'developer_connection_count': 'contributors'
})

# Debug: Check columns after renaming
print("Merged_df columns:", merged_df.columns.tolist())

# Filter based on thresholds and create a copy
threshold_metrics = [key.replace('min_', '') for key in thresholds.keys() if key.startswith('min_')]
filter_conditions = [merged_df[metric].fillna(0) >= thresholds[f'min_{metric}'] for metric in threshold_metrics if f'min_{metric}' in thresholds]
if filter_conditions:
    filter_mask = pd.concat(filter_conditions, axis=1).all(axis=1)
    eligible_df = merged_df[filter_mask].copy()
else:
    eligible_df = merged_df.copy()

# Ensure numeric data
metrics = list(weights.keys())
for metric in metrics:
    if metric in eligible_df.columns:
        eligible_df.loc[:, metric] = pd.to_numeric(eligible_df[metric], errors='coerce').fillna(0)

# Normalize metrics
for metric in metrics:
    if metric in eligible_df.columns:
        column_data = eligible_df[metric]
        min_val = column_data.min()
        max_val = column_data.max()
        if max_val > min_val:
            eligible_df.loc[:, f'normalized_{metric}'] = (eligible_df[metric] - min_val) / (max_val - min_val)
        else:
            eligible_df.loc[:, f'normalized_{metric}'] = 0
    else:
        print(f"Warning: Metric '{metric}' not found. Setting normalized value to 0.")
        eligible_df.loc[:, f'normalized_{metric}'] = 0

# Calculate weighted score
eligible_df.loc[:, 'score'] = sum(eligible_df[f'normalized_{metric}'].fillna(0) * weight for metric, weight in weights.items())

# Rank projects
ranked_df = eligible_df.sort_values(by='score', ascending=False)

output_directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'outputs')
output_path = os.path.join(output_directory, config['output']['rankings_file'])
os.makedirs(output_directory, exist_ok=True)

ranked_df.to_csv(output_path, index=False)
print(f"Ranking complete! Check '{output_path}' for results.")