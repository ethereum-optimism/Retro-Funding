import pandas as pd
import os
import glob


input_dir = os.path.dirname(os.path.abspath(__file__))
output_file = os.path.join(input_dir, "onchain__rewards_consolidated.csv")
csv_files = glob.glob(os.path.join(input_dir, "onchain__wvu_*_rewards.csv"))


dfs = {}
for file_path in csv_files:
    model_name = os.path.basename(file_path).split('__')[1].split('_rewards')[0]
    df = pd.read_csv(file_path)
    df = df[['project_id', 'project_name', 'display_name', 'op_reward']]
    df = df.rename(columns={'op_reward': f'op_reward__{model_name}'})
    dfs[model_name] = df

base_df = dfs[list(dfs.keys())[0]].copy()
for model_name, df in list(dfs.items())[1:]:
    base_df = pd.merge(
        base_df,
        df[['project_id', f'op_reward__{model_name}']],
        on='project_id',
        how='outer'
    )

base_df.to_csv(output_file, index=False)
print(f"\nAnalysis file saved to: {output_file}")
