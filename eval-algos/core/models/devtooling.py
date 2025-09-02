from dataclasses import dataclass
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
import yaml
import traceback
import warnings
import argparse
import os

from openrank_sdk import EigenTrust
import networkx as nx
warnings.filterwarnings('ignore', message='Defaulting to the \'raw\' score scale*')


# ------------------------------------------------------------------------
# Dataclass Definitions
# ------------------------------------------------------------------------

@dataclass
class DataSnapshot:
    """
    Contains file path details for devtooling and onchain project data.
    """
    data_dir: str
    onchain_projects_file: str
    devtooling_projects_file: str
    project_dependencies_file: str
    developers_to_projects_file: str
    utility_labels_file: str = None


@dataclass
class SimulationConfig:
    """
    Contains simulation parameters for the trust score computation.
    """
    alpha_onchain: float
    alpha_devtooling: float
    onchain_project_pretrust_weights: Dict[str, float]
    devtooling_project_pretrust_weights: Dict[str, float]
    link_type_time_decays: Dict[str, float]
    link_type_weights: Dict[str, float]
    event_type_weights: Dict[str, float]
    utility_weights: Dict[str, float]
    eligibility_thresholds: Dict[str, int]

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'SimulationConfig':
        """
        Creates a SimulationConfig instance from a dictionary, handling backwards compatibility.
        """
        sim_config = config_dict.get('simulation', {})
        
        # Handle backwards compatibility for alpha
        alpha = sim_config.get('alpha', 0.5)
        alpha_onchain = sim_config.get('alpha_onchain', alpha)
        alpha_devtooling = sim_config.get('alpha_devtooling', alpha)
        
        return cls(
            alpha_onchain=alpha_onchain,
            alpha_devtooling=alpha_devtooling,
            onchain_project_pretrust_weights=sim_config.get('onchain_project_pretrust_weights', {}),
            devtooling_project_pretrust_weights=sim_config.get('devtooling_project_pretrust_weights', {}),
            link_type_time_decays=sim_config.get('link_type_time_decays', {}),
            link_type_weights=sim_config.get('link_type_weights', {}),
            event_type_weights=sim_config.get('event_type_weights', {}),
            utility_weights=sim_config.get('utility_weights', {}),
            eligibility_thresholds=sim_config.get('eligibility_thresholds', {})
        )


# ------------------------------------------------------------------------
# DevtoolingCalculator Class
# ------------------------------------------------------------------------

class DevtoolingCalculator:
    """
    Calculates trust scores for devtooling projects based on their relationships with onchain projects.

    Trust Flow:
        1. Onchain projects (seeded with economic pretrust) confer trust to:
            - Devtooling projects via package dependencies.
            - Developers via commit events.
        2. Developers (seeded with reputation from onchain projects) confer trust to devtooling projects via GitHub engagement.

    The final EigenTrust propagation is seeded using a combination of:
        - Onchain project pretrust.
        - Developer reputation.
        - Devtooling project pretrust.
    """

    def __init__(self, config: SimulationConfig):
        """
        Initializes the DevtoolingCalculator with the given simulation configuration and an empty analysis dictionary.
        """
        self.config = config
        self.analysis = {}

    def run_analysis(
        self,
        df_onchain_projects: pd.DataFrame,
        df_devtooling_projects: pd.DataFrame,
        df_project_dependencies: pd.DataFrame,
        df_developers_to_projects: pd.DataFrame,
        utility_label_map: Dict[str, str],
        data_snapshot: DataSnapshot
    ) -> Dict[str, pd.DataFrame]:
        """
        Runs the complete analysis pipeline to compute trust scores.

        Args:
            df_onchain_projects (pd.DataFrame): DataFrame with onchain project data.
            df_devtooling_projects (pd.DataFrame): DataFrame with devtooling project data.
            df_project_dependencies (pd.DataFrame): DataFrame with project dependency relationships.
            df_developers_to_projects (pd.DataFrame): DataFrame with developer-project relationships.
            utility_label_map (Dict[str, str]): Mapping of project IDs to their utility categories.
            data_snapshot (DataSnapshot): Data snapshot containing file paths.

        Returns:
            Dict[str, pd.DataFrame]: Analysis dictionary containing intermediate and final outputs.
        """
        # Store raw input data
        self.analysis = {
            'onchain_projects': df_onchain_projects,
            'devtooling_projects': df_devtooling_projects,
            'project_dependencies': df_project_dependencies,
            'developers_to_projects': df_developers_to_projects,
            'utility_label_map': utility_label_map,
            'data_snapshot': data_snapshot
        }

        # Execute pipeline steps
        self._build_unweighted_graph() 
        self._compute_onchain_project_pretrust() 
        self._compute_devtooling_project_pretrust()
        self._compute_developer_reputation()
        self._weight_edges()
        #self._apply_eigentrust()
        self._apply_pagerank()
        self._rank_and_evaluate_projects()
        self._serialize_value_flow()

        return self.analysis

    # --------------------------------------------------------------------
    # Step 1: Construct an unweighted graph
    # --------------------------------------------------------------------
    def _build_unweighted_graph(self) -> None:
        """
        Builds an initial unweighted directed graph with the following edge types:
            - Package Dependency: Onchain projects → Devtooling projects.
            - Commit Events: Onchain projects → Developers.
            - GitHub Engagement: Developers → Devtooling projects.

        Removes duplicate edges when a developer's onchain project is also a devtooling project.
        The resulting edge list is stored in:
            self.analysis["unweighted_edges"]
        """
        df_onchain = self.analysis['onchain_projects'].copy()
        df_devtooling = self.analysis['devtooling_projects'].copy()
        df_dependencies = self.analysis['project_dependencies'].copy()
        df_devs2projects = self.analysis['developers_to_projects'].copy()

        # Create a mapping of project_id to display name
        project_mapping = {**df_onchain.set_index('project_id')['display_name'].to_dict(),
                           **df_devtooling.set_index('project_id')['display_name'].to_dict()}

        # Use the most recent event timestamp for decay calculations
        time_ref = df_devs2projects['event_month'].max()

        # --- Part 1: Package Dependency ---
        df_dependencies.rename(
            columns={
                'onchain_builder_project_id': 'i', 
                'devtooling_project_id': 'j',
                'dependency_source': 'event_type'
            },
            inplace=True
        )
        df_dependencies['event_month'] = time_ref
        df_dependencies['i_name'] = df_dependencies['i'].map(project_mapping)
        df_dependencies['j_name'] = df_dependencies['j'].map(project_mapping)
        df_dependencies['link_type'] = 'PACKAGE_DEPENDENCY'
        
        # --- Part 2: Commit Events ---
        df_devs2onchain = df_devs2projects[
            (df_devs2projects['project_id'].isin(df_onchain['project_id'])) &
            (df_devs2projects['event_type'] == 'COMMIT_CODE')
        ].copy()
        df_devs2onchain.rename(
            columns={
                'project_id': 'i',
                'developer_id': 'j',
                'developer_name': 'j_name'
            },
            inplace=True
        )
        df_devs2onchain['i_name'] = df_devs2onchain['i'].map(project_mapping)
        df_devs2onchain['link_type'] = 'ONCHAIN_PROJECT_TO_DEVELOPER'
        
        # --- Part 3: GitHub Engagement ---
        df_devs2tool = df_devs2projects[
            (df_devs2projects['project_id'].isin(df_devtooling['project_id']))
        ].copy()
        df_devs2tool.rename(
            columns={
                'developer_id': 'i',
                'project_id': 'j',
                'developer_name': 'i_name'
            },
            inplace=True
        )
        df_devs2tool['j_name'] = df_devs2tool['j'].map(project_mapping)
        df_devs2tool['link_type'] = 'DEVELOPER_TO_DEVTOOLING_PROJECT'
        
        # --- Remove Duplicate Edges ---
        onchain_devs_project_mapping = df_devs2onchain.set_index('j')['i'].to_dict()
        df_devs2tool['is_duplicate'] = df_devs2tool.apply(
            lambda row: row['i'] in onchain_devs_project_mapping and 
                        onchain_devs_project_mapping[row['i']] == row['j'], 
            axis=1
        )
        df_devs2tool = df_devs2tool[~df_devs2tool['is_duplicate']]
        df_devs2tool.drop(columns=['is_duplicate'], inplace=True)
        
        # --- Combine All Edges ---
        df_dependencies['link_type'] = 'PACKAGE_DEPENDENCY'
        df_devs2onchain['link_type'] = 'ONCHAIN_PROJECT_TO_DEVELOPER'
        df_devs2tool['link_type'] = 'DEVELOPER_TO_DEVTOOLING_PROJECT'
        df_combined = pd.concat([df_dependencies, df_devs2onchain, df_devs2tool], ignore_index=True)
        cols = ['i', 'j', 'i_name', 'j_name', 'link_type', 'event_type', 'event_month']
        self.analysis['unweighted_edges'] = df_combined[cols]

    # --------------------------------------------------------------------
    # Step 2: Seed onchain projects with economic pretrust
    # --------------------------------------------------------------------
    def _compute_onchain_project_pretrust(self) -> None:
        """
        Calculates pretrust scores for onchain projects using economic metrics.
        Applies log scaling and min-max normalization, then combines metrics with configured weights.
        
        Output is stored in:
            self.analysis["onchain_projects_pretrust_scores"]
        """
        df_onchain = self.analysis['onchain_projects'].copy()
        df_onchain.rename(columns={'project_id': 'i'}, inplace=True)
        
        wts = {k.lower(): v for k, v in self.config.onchain_project_pretrust_weights.items()}
        df_onchain['v'] = 0.0
        for col, weight in wts.items():
            if col in df_onchain.columns:
                df_onchain[col] = self._minmax_scale(np.log1p(df_onchain[col]))
                df_onchain['v'] += df_onchain[col] * weight
        
        onchain_total = df_onchain['v'].sum()
        df_onchain['v'] /= onchain_total
        self.analysis['onchain_projects_pretrust_scores'] = df_onchain

    # --------------------------------------------------------------------
    # Step 3: Seed devtooling projects with GitHub pretrust
    # --------------------------------------------------------------------
    def _compute_devtooling_project_pretrust(self) -> None:
        """
        Calculates pretrust scores for devtooling projects using GitHub metrics and graph-based metrics.
        Applies log scaling and min-max normalization, then combines metrics with configured weights.
        
        Output is stored in:
            self.analysis["devtooling_projects_pretrust_scores"]
        """
        df_devtooling = self.analysis['devtooling_projects'].copy()
        df_devtooling.rename(columns={'project_id': 'i'}, inplace=True)
        
        # Calculate graph-based metrics
        df_edges = self.analysis['unweighted_edges']
        
        # Calculate package connections
        package_connections = df_edges[df_edges['link_type'] == 'PACKAGE_DEPENDENCY'].groupby('j').size()
        df_devtooling['num_package_connections'] = df_devtooling['i'].map(package_connections).fillna(0)
        
        # Calculate developer connections
        developer_connections = df_edges[df_edges['link_type'] == 'DEVELOPER_TO_DEVTOOLING_PROJECT'].groupby('j').size()
        df_devtooling['num_developer_connections'] = df_devtooling['i'].map(developer_connections).fillna(0)
        
        wts = self.config.devtooling_project_pretrust_weights
        df_devtooling['v'] = 0.0
        for col, weight in wts.items():
            if col in df_devtooling.columns:
                df_devtooling[col] = self._minmax_scale(np.log1p(df_devtooling[col]))
                df_devtooling['v'] += df_devtooling[col] * weight
        
        devtooling_total = df_devtooling['v'].sum()
        df_devtooling['v'] /= devtooling_total
        self.analysis['devtooling_projects_pretrust_scores'] = df_devtooling

    # --------------------------------------------------------------------
    # Step 4: Compute developer reputation from onchain projects
    # --------------------------------------------------------------------
    def _compute_developer_reputation(self) -> None:
        """
        Distributes onchain project trust to developers based on commit events.
        The resulting developer reputation is normalized and stored in:
            self.analysis["developer_reputation"]
        """
        project_reputation = (
            self.analysis['onchain_projects_pretrust_scores']
            .set_index('i')['v']
            .to_dict()
        )
        commit_history = (
            self.analysis['unweighted_edges']
            .query('link_type == "ONCHAIN_PROJECT_TO_DEVELOPER"')
            .groupby(['event_month', 'j'])
            .i.unique()
        )
        reputation = {}
        for (event_month, developer), onchain_projects in commit_history.items():
            value = sum(project_reputation.get(src_project, 0) for src_project in onchain_projects)
            if len(onchain_projects) == 0:
                continue
            share = value / len(onchain_projects)
            reputation[developer] = reputation.get(developer, 0) + share

        df_dev_reputation = pd.DataFrame({
            'developer_id': list(reputation.keys()),
            'reputation': list(reputation.values())
        })
        dev_names = self.analysis['developers_to_projects'].set_index('developer_id')['developer_name'].to_dict()
        df_dev_reputation['developer_name'] = df_dev_reputation['developer_id'].map(dev_names)
        
        self.analysis['developer_reputation'] = df_dev_reputation

    # --------------------------------------------------------------------
    # Step 5: Weight edges (including time decay and utility weights)
    # --------------------------------------------------------------------
    def _weight_edges(self) -> None:
        """
        Applies configured weights and time decay to the graph edges based on recency.
        The weighted edges are stored in:
            self.analysis["weighted_edges"]
        """
        df_edges = self.analysis['unweighted_edges'].copy()
        df_edges['event_type'] = df_edges['event_type'].str.upper()

        # Get algorithm settings
        link_type_decay_factors = {k.upper(): v for k,v in self.config.link_type_time_decays.items()}
        event_type_weights = {k.upper(): v for k, v in self.config.event_type_weights.items()}
        utility_weights = self.config.utility_weights
        utility_label_map = self.analysis['utility_label_map']

        # Calculate time decay
        time_ref = df_edges['event_month'].max()    
        time_diff_years = (time_ref - df_edges['event_month']).dt.days / 365.0

        # Initialize with zero weights
        df_edges['v_edge'] = 0.0

        # Weight events by type and decay
        for link_type, decay_factor in link_type_decay_factors.items():
            mask = df_edges['link_type'] == link_type
            decay_lambda = np.log(2) / decay_factor
            
            # Get base weights from event type
            base_weights = df_edges.loc[mask, 'event_type'].map(event_type_weights)
            
            # Apply utility weights for devtooling projects
            if link_type == 'PACKAGE_DEPENDENCY':
                # For package dependencies, apply utility weight to the target project (j)
                # If project not in utility_label_map, use default weight of 1.0
                utility_weights_series = df_edges.loc[mask, 'j'].map(
                    lambda x: utility_weights.get(utility_label_map.get(x, ''), 1.0)
                )
                
                df_edges.loc[mask, 'v_edge'] = (
                    np.exp(-decay_lambda * time_diff_years[mask])
                    * base_weights
                    * utility_weights_series
                )
            elif link_type == 'DEVELOPER_TO_DEVTOOLING_PROJECT':
                # For developer to devtooling project links, apply utility weight to the target project (j)
                # If project not in utility_label_map, use default weight of 1.0
                utility_weights_series = df_edges.loc[mask, 'j'].map(
                    lambda x: utility_weights.get(utility_label_map.get(x, ''), 1.0)
                )
                
                df_edges.loc[mask, 'v_edge'] = (
                    np.exp(-decay_lambda * time_diff_years[mask])
                    * base_weights
                    * utility_weights_series
                )
            else:
                # For other link types, just apply time decay and event weights
                df_edges.loc[mask, 'v_edge'] = (
                    np.exp(-decay_lambda * time_diff_years[mask])
                    * base_weights
                )

        # Save the weighted edges
        self.analysis['weighted_edges'] = df_edges

    # --------------------------------------------------------------------
    # Step 6A: Apply EigenTrust propagation
    # --------------------------------------------------------------------
    def _apply_eigentrust(self) -> None:
        """
        Combines pretrust scores from onchain projects, devtooling projects, and developer reputation,
        and applies the EigenTrust algorithm to propagate trust scores through the weighted graph.
        
        The resulting scores are stored in:
            self.analysis["project_openrank_scores"]

        Raises:
            ValueError: If no edge records or pretrust scores are found.
        """
        et_onchain = EigenTrust(alpha=self.config.alpha_onchain)
        et_devtooling = EigenTrust(alpha=self.config.alpha_devtooling)

        # Get pretrust scores
        pretrust_list = []
        onchain = self.analysis.get('onchain_projects_pretrust_scores', pd.DataFrame())
        if not onchain.empty:
            pretrust_list.extend({'i': row['i'], 'v': row['v']} for _, row in onchain.iterrows() if row['v'] > 0)
        
        devtooling = self.analysis.get('devtooling_projects_pretrust_scores', pd.DataFrame())
        if not devtooling.empty:
            pretrust_list.extend({'i': row['i'], 'v': row['v']} for _, row in devtooling.iterrows() if row['v'] > 0)
        devtooling_ids = devtooling['i'].unique()
        
        developers = self.analysis.get('developer_reputation', pd.DataFrame())
        if not developers.empty:
            pretrust_list.extend({'i': row['developer_id'], 'v': row['reputation']} for _, row in developers.iterrows() if row['reputation'] > 0)

        df_edges = self.analysis['weighted_edges'].copy()
        df_edges = df_edges[df_edges['v_edge'] > 0]

        # Pass 1: Run EigenTrust on package dependency links
        package_edge_records = [
            {'i': row['i'], 'j': row['j'], 'v': row['v_edge']}
            for _, row in df_edges.iterrows()
            if row['link_type'] == 'PACKAGE_DEPENDENCY'
        ]
        package_scores = et_onchain.run_eigentrust(package_edge_records, pretrust_list)
        df_package_scores = pd.DataFrame(package_scores, columns=['i', 'v'])
        df_package_scores = df_package_scores[df_package_scores['i'].isin(devtooling_ids)]
        df_package_scores['v'] = df_package_scores['v'] / df_package_scores['v'].sum()
        df_package_scores['link_type'] = 'PACKAGE_DEPENDENCY'

        # Pass 2: Run EigenTrust on developer links
        developer_edge_records = [
            {'i': row['i'], 'j': row['j'], 'v': row['v_edge']}
            for _, row in df_edges.iterrows()
            if row['link_type'] in ['ONCHAIN_PROJECT_TO_DEVELOPER', 'DEVELOPER_TO_DEVTOOLING_PROJECT']
        ]
        developer_scores = et_devtooling.run_eigentrust(developer_edge_records, pretrust_list)
        df_developer_scores = pd.DataFrame(developer_scores, columns=['i', 'v'])
        df_developer_scores = df_developer_scores[df_developer_scores['i'].isin(devtooling_ids)]
        df_developer_scores['v'] = df_developer_scores['v'] / df_developer_scores['v'].sum()
        df_developer_scores['link_type'] = 'DEVELOPER_TO_DEVTOOLING_PROJECT'

        # Apply link type weights and normalize again
        link_type_weights = {k.upper(): v for k, v in self.config.link_type_weights.items()}
        df_scores_pre = pd.concat([df_package_scores, df_developer_scores])
        df_scores_pre['v'] = df_scores_pre['v'] * df_scores_pre['link_type'].map(link_type_weights)
        df_scores = df_scores_pre.groupby('i', as_index=False)['v'].sum()
        df_scores['v'] = df_scores['v'] / df_scores['v'].sum()
        
        df_scores.set_index('i', inplace=True)
        self.analysis['project_openrank_scores'] = df_scores

    # --------------------------------------------------------------------
    # Step 6B: Apply PageRank propagation
    # --------------------------------------------------------------------

    def _apply_pagerank(self) -> None:
        """
        Uses weighted PageRank (with personalised teleport vector) to propagate
        trust from onchain projects and developers to devtooling projects.

        Results are written to ``self.analysis["project_openrank_scores"]`` as
        before so that subsequent steps remain unchanged.
        """
        # ---- 6a. Build the personalised teleport (pre‑trust) vector --------
        pretrust = {}

        def _add_pretrust(df: pd.DataFrame, id_col: str, weight_col: str):
            nonlocal pretrust
            if df.empty:
                return
            for _, row in df.iterrows():
                if row[weight_col] > 0:
                    pretrust[row[id_col]] = pretrust.get(row[id_col], 0.0) + row[weight_col]

        _add_pretrust(self.analysis.get("onchain_projects_pretrust_scores", pd.DataFrame()), "i", "v")
        _add_pretrust(self.analysis.get("devtooling_projects_pretrust_scores", pd.DataFrame()), "i", "v")
        _add_pretrust(self.analysis.get("developer_reputation", pd.DataFrame()), "developer_id", "reputation")

        if not pretrust:
            raise ValueError("No pre‑trust scores available for PageRank.")

        # ---- 6b. Extract the weighted edge list --------------------------------
        df_edges = self.analysis["weighted_edges"].query("v_edge > 0").copy()

        # Two separate passes (package & developer) to maintain existing weighting strategy
        results = []
        passes = {
            "PACKAGE_DEPENDENCY": {
                "alpha": self.config.alpha_onchain,   # damping factor
                "edges": df_edges.query("link_type == 'PACKAGE_DEPENDENCY'"),
            },
            "DEVELOPER": {
                "alpha": self.config.alpha_devtooling,
                "edges": df_edges.query("link_type in ['ONCHAIN_PROJECT_TO_DEVELOPER', "
                                        "'DEVELOPER_TO_DEVTOOLING_PROJECT']"),
            },
        }

        for pass_name, spec in passes.items():
            g = nx.DiGraph()
            g.add_weighted_edges_from(
                spec["edges"][["i", "j", "v_edge"]].itertuples(index=False, name=None)
            )

            # Normalise pretrust so it sums to 1 and only contains nodes present in this sub‑graph
            sub_nodes = set(g.nodes())
            personalisation = {n: pretrust.get(n, 0.0) for n in sub_nodes}
            total = sum(personalisation.values())
            if total == 0:
                # fall back to uniform vector
                personalisation = None
            else:
                personalisation = {k: v / total for k, v in personalisation.items()}

            pr_scores = nx.pagerank(
                g,
                alpha=spec["alpha"],         # damping = 1 – teleport prob
                personalization=personalisation,
                weight="weight",
                max_iter=100,
                tol=1.0e-08,
            )

            # Write out as DataFrame
            df_pr = (
                pd.Series(pr_scores, name="v")
                .reset_index()
                .rename(columns={"index": "i"})
            )
            if pass_name == "PACKAGE_DEPENDENCY":
                df_pr["link_type"] = "PACKAGE_DEPENDENCY"
            else:
                df_pr["link_type"] = "DEVELOPER_TO_DEVTOOLING_PROJECT"
            # Keep only dev‑tooling projects for downstream ranking
            devtooling_ids = self.analysis["devtooling_projects_pretrust_scores"]["i"].unique()
            df_pr = df_pr[df_pr["i"].isin(devtooling_ids)]
            # Re‑normalise so each pass sums to 1
            df_pr["v"] = df_pr["v"] / df_pr["v"].sum()
            results.append(df_pr)

        # ---- 6c. Combine the two passes using configured link‑type weights ----
        df_scores = pd.concat(results, ignore_index=True)

        link_type_weights = {k.upper(): v for k, v in self.config.link_type_weights.items()}
        df_scores["v"] *= df_scores["link_type"].map(link_type_weights).fillna(1.0)
        df_scores = df_scores.groupby("i", as_index=False)["v"].sum()
        df_scores["v"] /= df_scores["v"].sum()  # global normalisation

        # Preserve previous interface
        self.analysis["project_openrank_scores"] = df_scores.set_index("i")


    # --------------------------------------------------------------------
    # Step 7: Rank and evaluate devtooling projects
    # --------------------------------------------------------------------
    def _rank_and_evaluate_projects(self) -> None:
        """
        Ranks projects based on OpenRank scores and additional metrics (dependency counts, developer links)
        and applies eligibility thresholds. The final rankings are stored in:
            self.analysis["devtooling_project_results"]
        """
        df_results = self.analysis['devtooling_projects'].copy()
        df_scores = self.analysis['project_openrank_scores'].copy()
        df_edges = self.analysis['weighted_edges']

        df_pkg_deps = df_edges[df_edges['link_type'] == 'PACKAGE_DEPENDENCY']
        df_results['total_dependents'] = df_results['project_id'].apply(
            lambda pid: df_pkg_deps[df_pkg_deps['j'] == pid]['i'].nunique()
        )
        
        df_dev_links = df_edges[df_edges['link_type'] == 'DEVELOPER_TO_DEVTOOLING_PROJECT']
        df_results['developer_links'] = df_results['project_id'].apply(
            lambda pid: df_dev_links[df_dev_links['j'] == pid]['i'].nunique()
        )
        
        thresholds = self.config.eligibility_thresholds
        df_results['is_eligible'] = 0
        df_results.loc[
            (df_results['total_dependents'] >= thresholds.get('num_projects_with_package_links', 0)) |
            (df_results['developer_links'] >= thresholds.get('num_onchain_developers_with_links', 0)),
            'is_eligible'
        ] = 1
        
        # Reset index to make 'i' a column for merging
        df_scores_reset = df_scores.reset_index()
        df_results = df_results.merge(df_scores_reset, left_on='project_id', right_on='i', how='left')

        df_results['v'] = df_results['v'].fillna(0.0)
        df_results.drop_duplicates(subset=['project_id'], inplace=True)

        df_results['v_aggregated'] = df_results['v'] * df_results['is_eligible']
        total_score = df_results['v_aggregated'].sum()
        if total_score > 0:
            df_results['v_aggregated'] /= total_score
            
        df_results.sort_values(by='v_aggregated', ascending=False, inplace=True)
        self.analysis['devtooling_project_results'] = df_results

    # --------------------------------------------------------------------
    # Step 8: Serialize detailed value flow graph
    # --------------------------------------------------------------------
    def _serialize_value_flow(self) -> None:
        """
        Constructs a detailed graph showing the contribution flow between onchain and devtooling projects.
        Uses iterative proportional fitting (IPF) to allocate contributions so that:
            - For each devtooling project, contributions sum to its v_aggregated.
            - For each onchain project, contributions sum to its economic pretrust v.
        
        Output is stored in:
            self.analysis["detailed_value_flow_graph"]

        Warnings are issued if contribution sums do not match the targets.
        """
        import warnings  # Ensure warnings is imported
        
        edges = self.analysis['weighted_edges']
        results = self.analysis['devtooling_project_results']
        onchain_projects = self.analysis['onchain_projects_pretrust_scores']

        onchain_projects_by_dev = (
            edges.query('link_type == "ONCHAIN_PROJECT_TO_DEVELOPER"')
                 .groupby('j')['i']
                 .unique()
                 .to_dict()
        )
        
        df_pkg = edges.loc[edges['link_type'] == 'PACKAGE_DEPENDENCY', ['i', 'j']].copy()

        df_dev = edges.loc[edges['link_type'] == 'DEVELOPER_TO_DEVTOOLING_PROJECT', ['i', 'j']].copy()
        df_dev['onchain_list'] = df_dev['i'].map(lambda d: onchain_projects_by_dev.get(d, []))
        df_dev_expanded = df_dev.explode('onchain_list')
        df_dev_expanded = df_dev_expanded[['onchain_list', 'j']].rename(columns={'onchain_list': 'i'})
        
        graph_df = pd.concat([df_pkg, df_dev_expanded], ignore_index=True)
        
        counts = graph_df.groupby(['i', 'j']).size().reset_index(name='count')
        pivot = counts.pivot(index='i', columns='j', values='count').fillna(0)
        onchain_ids = pivot.index.to_numpy()
        devtooling_ids = pivot.columns.to_numpy()
        A = pivot.values

        devtooling_project_scores = results.set_index('project_id')['v_aggregated'].to_dict()
        onchain_project_scores = onchain_projects.set_index('i')['v'].to_dict()
        v_onchain = np.array([onchain_project_scores.get(i, 0) for i in onchain_ids])
        v_devtooling = np.array([devtooling_project_scores.get(j, 0) for j in devtooling_ids])
        
        s = np.ones(len(devtooling_ids))
        tol = 1e-6
        max_iter = 1000
        for _ in range(max_iter):
            r = v_onchain / (A.dot(s) + 1e-12)
            s_new = v_devtooling / (A.T.dot(r) + 1e-12)
            if np.allclose(s_new, s, atol=tol):
                s = s_new
                break
            s = s_new
        
        X = A * r[:, np.newaxis] * s[np.newaxis, :]
        
        i_idx, j_idx = np.nonzero(X)
        contributions = X[i_idx, j_idx]
        detailed_df = pd.DataFrame({
            'onchain_project_id': onchain_ids[i_idx],
            'devtooling_project_id': devtooling_ids[j_idx],
            'contribution': contributions
        })
        
        dev_sum = detailed_df.groupby('devtooling_project_id')['contribution'].sum().round(6)
        for j in devtooling_ids:
            target = devtooling_project_scores.get(j, 0)
            if abs(dev_sum.get(j, 0) - target) > 1e-4:
                pass
                #warnings.warn(f"Devtooling project {j} total contribution {dev_sum.get(j, 0)} != target {target}")
        
        onchain_sum = detailed_df.groupby('onchain_project_id')['contribution'].sum().round(6)
        for i in onchain_ids:
            target = onchain_project_scores.get(i, 0)
            if abs(onchain_sum.get(i, 0) - target) > 1e-4:
                pass
                #warnings.warn(f"Onchain project {i} total contribution {onchain_sum.get(i, 0)} != target {target}")
        
        self.analysis['detailed_value_flow_graph'] = detailed_df

    # --------------------------------------------------------------------
    # Helper: MinMax Scaling (Static Method)
    # --------------------------------------------------------------------
    @staticmethod
    def _minmax_scale(values: pd.Series) -> pd.Series:
        """
        Applies min-max scaling to a series of numeric values.

        Args:
            values (pd.Series): Input series.

        Returns:
            pd.Series: Scaled series with values in the range [0, 1].
        """
        vmin, vmax = values.min(), values.max()
        if vmax == vmin:
            return pd.Series([0.5] * len(values), index=values.index)
        return (values - vmin) / (vmax - vmin)


# ------------------------------------------------------------------------
# Helper Functions for Configuration and Data Loading
# ------------------------------------------------------------------------

def load_config(config_path: str) -> Tuple[DataSnapshot, SimulationConfig]:
    """
    Loads configuration from a YAML file.

    Args:
        config_path (str): Path to the YAML configuration file.

    Returns:
        Tuple[DataSnapshot, SimulationConfig]: The loaded DataSnapshot and SimulationConfig objects.
    """
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    data_snapshot = DataSnapshot(
        data_dir=config['data_snapshot']['data_dir'],
        onchain_projects_file=config['data_snapshot']['onchain_projects'],
        devtooling_projects_file=config['data_snapshot']['devtooling_projects'],
        project_dependencies_file=config['data_snapshot']['project_dependencies'],
        developers_to_projects_file=config['data_snapshot']['developers_to_projects'],
        utility_labels_file=config['data_snapshot'].get('utility_labels')
    )

    simulation_config = SimulationConfig.from_dict(config)
    return data_snapshot, simulation_config


def load_data(data_snapshot: DataSnapshot) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, str]]:
    """
    Loads data files specified in the DataSnapshot.

    Args:
        data_snapshot (DataSnapshot): Object containing file path details.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, str]]: DataFrames for onchain projects,
        devtooling projects, project dependencies, developer-project relationships, and utility label mapping.
    """
    def get_path(filename: str) -> str:
        return os.path.join(data_snapshot.data_dir, filename)

    df_onchain_projects = pd.read_csv(get_path(data_snapshot.onchain_projects_file))
    df_devtooling_projects = pd.read_csv(get_path(data_snapshot.devtooling_projects_file))
    df_project_dependencies = pd.read_csv(get_path(data_snapshot.project_dependencies_file))
    
    df_developers_to_projects = pd.read_csv(get_path(data_snapshot.developers_to_projects_file))
    if 'event_month' in df_developers_to_projects.columns:
        df_developers_to_projects['event_month'] = pd.to_datetime(df_developers_to_projects['event_month'])
    elif 'bucket_month' in df_developers_to_projects.columns:
        df_developers_to_projects['event_month'] = pd.to_datetime(df_developers_to_projects['bucket_month'])
    else:
        raise ValueError("No 'event_month' or 'bucket' column found in developers_to_projects.csv")

    # Load and join utility labels if available
    utility_label_map = {}
    if data_snapshot.utility_labels_file:
        try:
            df_utility_labels = pd.read_csv(get_path(data_snapshot.utility_labels_file))
            df_joined = pd.merge(
                df_utility_labels,
                df_devtooling_projects[['project_id', 'project_name']],
                on='project_name',
                how='left'
            )
            utility_label_map = df_joined.set_index('project_id')['recommendation'].to_dict()
        except (KeyError, FileNotFoundError) as e:
            warnings.warn(f"Utility labels not found: {str(e)}. Using default weight of 1.0 for all projects.")

    return (df_onchain_projects, df_devtooling_projects,
            df_project_dependencies, df_developers_to_projects,
            utility_label_map)


def run_simulation(config_path: str) -> Dict[str, Any]:
    """
    Runs the complete simulation pipeline for devtooling trust score calculation.

    Args:
        config_path (str): Path to the YAML configuration file.

    Returns:
        Dict[str, Any]: Analysis dictionary including all intermediate outputs and final results.
    """
    data_snapshot, simulation_config = load_config(config_path)
    data = load_data(data_snapshot)
    calculator = DevtoolingCalculator(simulation_config)
    analysis = calculator.run_analysis(*data, data_snapshot)
    analysis["data_snapshot"] = data_snapshot
    analysis["simulation_config"] = simulation_config
    return analysis


def save_results(analysis: Dict[str, Any]) -> None:
    """
    Saves analysis results to CSV files and logs the outcome.

    Args:
        analysis (Dict[str, Any]): Analysis dictionary containing the results.
    """
    data_snapshot = analysis.get("data_snapshot")
    if data_snapshot is None:
        print("No DataSnapshot found; skipping file output.")
        return

    # Save devtooling OpenRank results
    results_path = f"{data_snapshot.data_dir}/devtooling_openrank_results.csv"
    final_results = analysis.get("devtooling_project_results")
    if final_results is not None:
        final_results.to_csv(results_path, index=False)
        print(f"[INFO] Saved devtooling openrank results to {results_path}")
    else:
        print("[WARN] No 'final_results' to serialize.")

    # Save detailed graph data
    graph_path = f"{data_snapshot.data_dir}/detailed_devtooling_graph.csv"
    graph_data = analysis.get("weighted_edges")
    if graph_data is not None:
        graph_data.to_csv(graph_path, index=False)
        print(f"[INFO] Saved detailed graph to {graph_path}")
    else:
        print("[WARN] No 'detailed_graph' to serialize.")

    # Save value flow data
    export_path = f"{data_snapshot.data_dir}/value_flow_sankey.csv"
    detailed_df = analysis.get("detailed_value_flow_graph")
    if detailed_df is not None:
        detailed_df.to_csv(export_path, index=False)
        print(f"[INFO] Saved sankey data to {export_path}")
    else:
        print("[WARN] No 'detailed_value_flow_graph' to serialize.")


def main():
    """
    Standard entry-point for running the devtooling openrank analysis pipeline.
    Accepts a YAML filename as a command line argument.
    """
    parser = argparse.ArgumentParser(description='Run devtooling openrank analysis pipeline')
    parser.add_argument('yaml_file', nargs='?', default='devtooling_openrank_testing.yaml',
                      help='Name of YAML file in weights directory (default: devtooling_openrank_testing.yaml)')
    args = parser.parse_args()
    
    config_path = f'eval-algos/S7/weights/{args.yaml_file}'
    try:
        analysis = run_simulation(config_path)
        save_results(analysis)
    except Exception as e:
        print(f"[ERROR] Error during simulation: {str(e)}")
        traceback.print_exc()


if __name__ == "__main__":
    main()