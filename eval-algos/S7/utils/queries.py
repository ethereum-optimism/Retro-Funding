"""
This module contains all the SQL queries used to fetch data from OSO.
"""

THIS_PERIOD = 'M6'
THIS_PERIOD_NUMBER = THIS_PERIOD[-1]
START_DATE = '2024-11-01'
END_DATE = '2025-08-01'
THIS_PERIOD_DATE = '2025-07-01'
LAST_PERIOD_DATE = '2025-06-01'
FLAG_LIST = [
    '0xaa1b878800206da24ee7297fb202ef98a6af0fb3ec298a65ba6b675cb4f4144b', # Test Project
    '0x482720e73e91229b5f7d5e2d80a54eb8a722309c26dba03355359788b18f4373', # M4 RubyScore (manufactured activity)
    '0x03f730811b2a61aa1e8f7bdb6676e4027ed2b8f10bb731789a5d10e5ddc1352c', # M6 Onchain Heritage (manufactured activity)
    '0x076a2b1418a515ff8c5bb11beed5630cc6fe7f65fd8d42d4403c4364514f2a30', # M6 BAG Guild Dapp (manufactured activity)
    '0xcae812d91b7b86edf3141f44f006e8a03931ebc489e0a417b82b603bf325bc96', # M6 World MiniApps - NFT and Gaming (no in-store Mini App)
]
TRANSITIVE_DEPENDENCY_LIST = [
    'pr9u5w1LqcK44g1o2RcI9ztDGB8nZTkJYMOq7e8pvac=', # noble-cryptography
    'ISJwb3A6NNTyxbFJnVHANLlnawWh8kDARUXf4HZTd3s=', # ethereum-bloom-filters
]
METRICS = [
    'average_tvl_monthly',
    'amortized_contract_invocations_monthly',
    'gas_fees_monthly',
    'active_farcaster_users_monthly',
    'qualified_addresses_monthly',
    'contract_invocations_upgraded_eoa_monthly',
]

stringify = lambda arr: "'" + "','".join(arr) + "'"

QUERIES = [
    {
        "filename": "onchain__project_metadata",
        "filetype": "csv",
        "query": f"""
            SELECT
                p.project_id,
                p.project_name,
                p.display_name,
                e.transaction_count,
                e.gas_fees,
                e.active_days,
                (e.meets_all_criteria AND NOT (p.project_name IN ({stringify(FLAG_LIST)}))) AS is_eligible
            FROM int_superchain_s7_onchain_builder_eligibility AS e
            JOIN projects_v1 AS p ON e.project_id = p.project_id
            JOIN projects_by_collection_v1 AS pbc ON p.project_id = pbc.project_id
            WHERE
                pbc.collection_name = '8-{THIS_PERIOD_NUMBER}'
                AND e.sample_date = DATE '{THIS_PERIOD_DATE}'
            ORDER BY e.transaction_count DESC
        """
    },
    {
        "filename": "onchain__metrics_by_project",
        "filetype": "csv",
        "query": f"""
            SELECT
                m.project_id,
                p.display_name,
                pbc.project_name,
                m.chain,
                m.metric_name,
                DATE_FORMAT(m.sample_date, '%Y-%m-%d') AS sample_date,
                DATE_FORMAT(m.sample_date, '%b %Y') AS measurement_period,
                m.amount
            FROM int_superchain_s7_onchain_metrics_by_project AS m
            JOIN projects_by_collection_v1 AS pbc ON m.project_id = pbc.project_id
            JOIN projects_v1 AS p ON pbc.project_id = p.project_id
            WHERE
                pbc.collection_name = '8-{THIS_PERIOD_NUMBER}'
                AND m.sample_date >= DATE ('{LAST_PERIOD_DATE}')
                AND m.sample_date < DATE '{END_DATE}'
                AND m.metric_name IN ({stringify(METRICS)})
        """
    },
    {
        "filename": "devtooling__project_metadata",
        "filetype": "csv",
        "query": f"""
            SELECT 
                project_id,
                project_name,
                display_name,
                fork_count,
                star_count,
                num_packages_in_deps_dev
            FROM int_superchain_s7_devtooling_metrics_by_project
            ORDER BY fork_count DESC
        """
    },
    {
        "filename": "devtooling__onchain_metadata",
        "filetype": "csv",
        "query": f"""
            SELECT DISTINCT
                b.project_id,
                p.project_name,
                p.display_name,
                MAX(b.total_transaction_count) AS total_transaction_count,
                MAX(b.total_gas_fees) AS total_gas_fees
            FROM int_superchain_s7_devtooling_onchain_builder_nodes AS b
            JOIN projects_v1 AS p ON b.project_id = p.project_id
            GROUP BY 1, 2, 3
            ORDER BY 4 DESC
        """
    },
    {
        "filename": "devtooling__dependency_graph",
        "filetype": "csv",
        "query": f"""
            SELECT
              onchain_builder_project_id,
              devtooling_project_id,
              CASE
                WHEN devtooling_project_id IN ({stringify(TRANSITIVE_DEPENDENCY_LIST)})
                  AND dependency_source = 'NPM'
                THEN 'NPM_TRANSITIVE'
                ELSE dependency_source
              END AS dependency_source
            FROM int_superchain_s7_devtooling_deps_to_projects_graph
        """
    },
    {
        "filename": "devtooling__developer_graph",
        "filetype": "csv",
        "query": f"""
            SELECT *
            FROM int_superchain_s7_devtooling_devs_to_projects_graph
            WHERE project_id != '8Cgztczct8fnsJW6D2OQcFRY6nClKNyOC7Le0soED94='
        """
    },
    {
        "filename": "devtooling__raw_metrics",
        "filetype": "json",
        "query": f"""
            SELECT * 
            FROM int_superchain_s7_devtooling_metrics_by_project
        """
    },
    {
        "filename": "onchain__summary_metric_snapshot",
        "filetype": "csv",
        "query": f"""
            WITH params AS (
                SELECT DATE '{THIS_PERIOD_DATE}' AS month_start
            )
            SELECT
                tm.project_id,
                p.project_name AS op_atlas_id,
                p.display_name,
                LOWER(
                    REGEXP_REPLACE(
                      (CASE
                        WHEN m.metric_name = 'WORLDCHAIN_worldchain_users_aggregation_daily' THEN 'Active Addresses Aggregation'
                        WHEN m.metric_name = 'WORLDCHAIN_gas_fees_internal_daily' THEN 'Gas Fees'
                        ELSE m.display_name
                      END),
                      '[^a-zA-Z0-9]+',
                      '_'
                    )
                ) || '__' ||
                LOWER(DATE_FORMAT(tm.sample_date, '%b')) || '_' || 
                DATE_FORMAT(tm.sample_date, '%Y')
                AS metric_name,

                DATE_FORMAT(tm.sample_date, '%b %Y') AS measurement_period,

                SUM(
                    CASE
                        WHEN m.display_name IN ('Defillama TVL', 'Active Addresses Aggregation', 'Worldchain Users Aggregation')
                        THEN tm.amount / DAY(LAST_DAY_OF_MONTH(tm.sample_date))
                        ELSE tm.amount
                    END
                ) AS amount
            FROM timeseries_metrics_by_project_v0 AS tm
            JOIN metrics_v0 AS m ON m.metric_id = tm.metric_id
            JOIN projects_v1 AS p ON p.project_id = tm.project_id
            JOIN projects_by_collection_v1 AS pbc ON pbc.project_id = p.project_id
            CROSS JOIN int_superchain_chain_names AS chains
            JOIN params AS pms ON TRUE
            WHERE
                pbc.collection_name = '8-5'
            AND tm.sample_date >= pms.month_start
            AND tm.sample_date < DATE_ADD('month', 1, pms.month_start)
            AND m.metric_name LIKE CONCAT(chains.chain, '%')
            AND (
                m.metric_name LIKE '%gas_fees_daily'
                OR m.metric_name LIKE '%defillama_tvl_daily'
                OR m.metric_name LIKE '%active_addresses_aggregation_daily'
                OR m.metric_name LIKE '%contract_invocations_daily'
                OR m.metric_name LIKE '%contract_invocations_daily'
                OR m.metric_name = 'WORLDCHAIN_worldchain_users_aggregation_daily'
                OR m.metric_name = 'WORLDCHAIN_gas_fees_internal_daily'
            )
            GROUP BY 1, 2, 3, 4, 5
        """
    }
] 