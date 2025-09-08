# Changelog

All notable changes to algorithms, weights, and underlying OSO models will be documented here.

## [M7] - 2025-09-08

_This is the first reward round for Season 8 (S8). Note that the total budgets for both Onchain Builders and Dev Tooling have been reduced in S8 compared to S7._

### Added
- Core utilities for running the complete pipeline for a given season and measurement period.
- A logo manager utility for downloading, resizing, and saving logos for all projects in a given season and measurement period.

### Changed
- Onchain builders:
  - The total monthly reward budget has been reduced from 1,300,000 OP to 166,666.67 OP.
  - Projects with monthly Superchain TVL above $100M are now excluded from rewards.
  - The `max_share_per_project` has been reduced from 0.05 to 0.03.
  - The `percentile_cap` has been reduced from 98.5 to 97.5.
  - The metric inputs have been set to `contract_invocations` = 0.35, `gas_fees` = 0.35, and `qualified_users` = 0.30.
- Dev Tooling:
  - The total monthly reward budget has been reduced from 1,300,000 OP to 500,000 OP.
  - The starting period under consideration for recent developer activity has been pushed forward by 6 months (eg, from 2024-01-01 to 2024-07-01).
  - The `max_share_per_project` has been reduced from 0.06 to 0.05.

### Fixed
- Tighter filtering to ensure that only activity on the 19 targeted chains is factored into rewards.
- Amortized Layer 2 gas fees are now being calculated directly using `receipts` data in the OSO pipeline. This change should produce more accurate gas estimations for projects on a given chain.

## [M6] - 2025-08-04

### Added
- Added support for PageRank propagation in devtooling project links.

### Changed
- Onchain builders:
  - Adjusted metric variant weights: `growth` increased from 0.20 to 0.30, `retention` decreased from 0.60 to 0.50.
  - Identified and removed 3 projects that were manufacturing activity.
- Dev Tooling:
  - Rebalanced devtooling project pretrust weights to emphasize developer connections: `num_package_connections` decreased from 0.40 to 0.30, `num_developer_connections` increased from 0.60 to 0.70.
  - Reduced link type time decay for `developer_to_devtooling_project` from 0.80 to 0.60 to increase the influence of recent developer activity.
  - Decreased `package_dependency` link type weight from 1.5 to 1.0

### Fixed
- Related projects (ie, projects that are maintained by the same team, share the same deployer, and operate on the same chain) are now aggregated into a single project, generally the first one to have applied to the round. This change affects a small number of World Mini Apps.

## [M5] - 2025-07-07

### Added
- Added support for [transitive NPM dependencies](https://github.blog/changelog/2025-03-04-easily-distinguish-between-direct-and-transitive-dependencies-for-npm-packages/) in devtooling project links.
- Added new onchain builder metric: `contract_invocations_upgraded_eoa_monthly`. This metric is used to track the number of contract invocations made from EIP-7702 upgraded EOAs.

### Changed
- Onchain builders:
  - Set initial weight for `contract_invocations_upgraded_eoa_monthly` to 0.07702 and reduced weight for `amortized_contract_invocations_monthly` from 0.275 to 0.19798.
  - Increased weight for `average_tvl_monthly` from 0.275 to 0.30.
  - Reduced `qualified_addresses_monthly` weight from 0.175 to 0.15.
  - Increased the `percentile_cap` from 98 to 98.5.
- Dev Tooling:
  - Set initial weight for `npm_transitive` to 0.1.
  - Applied the `npm_transitive` weight to projects that had more than 10 package links and more than 90% of these links are transitive.

### Fixed
- Created more consistent contract discovery and de-duplication logic for onchain builders in the OSO models.

## [M4] - 2025-06-15

### Added
- Added graph-based metrics to devtooling project pretrust weights: `num_package_connections` and `num_developer_connections`.
- Introduced separate trust propagation rates for onchain and devtooling projects via `alpha_onchain` and `alpha_devtooling` parameters.
- Shell utility script for running the complete pipeline.

### Changed
- Reduced total budgets from 1,333,333.33 to 1,300,000 OP.
- Onchain builders:
  - Updated onchain builder metric weights to increase emphasis on core metrics:
    - Increased weights for contract invocations, gas fees, and TVL from 0.25 to 0.275 each
    - Reduced overall weight for user metrics from 0.25 to 0.175
- Dev Tooling:
  - Modified devtooling project pretrust weights to focus entirely on graph-based metrics:
    - Removed GitHub metrics (stars, forks, deps.dev packages)
    - Added new weights: `num_package_connections: 0.40`, `num_developer_connections: 0.60`
  - Increased utility weights for 'Core Protocol Interfaces' and 'Development Frameworks' from 4.00 to 5.00
  - Increased maximum share per project from 5% to 6%

### Fixed
- Enabled backwards compatibility for configuration loading with new alpha parameters.
- Updated queries to use the latest OSO data and suppress duplicate DefiLlama slugs introduced due to Atlas bug.

## [M3] - 2025-05-19

### Added
- Generated utility labels for all devtooling projects.
- Added `utility_weights` parameter to `devtooling__arcturus.yaml` to control utility label weights.
- Included World Verified Users in the `qualified_addresses_monthly` metric within `onchain__goldilocks.yaml`.

### Changed
- Reduced `link_type_weights` for `package_dependency` from 3.0 to 1.5 in `devtooling__arcturus.yaml` to reflect high utility weightings for packages.
- Increased the `percentile_cap` in `onchain__goldilocks.yaml` from 97 to 98.

### Fixed
- Corrected OSO-side logic for building the developer graph: developers tied to onchain contracts in separate GitHub organizations no longer receive links to devtooling projects.
- Improved handling of projects that share a root deployer but deploy contracts across multiple repositories.
- Fixed one case of a DefiLlama slug being misattributed to the wrong project.

## [M2] - 2025-04-28

### Added
- Introduced new onchain-builder weighting metrics options (e.g., World Verified Users and Account Abstraction UserOps); these currently have no explicit weightings in M2.
- Added Worldchain-specific event handling for UserOps.
- Developed utility scripts for fetching OSO data and generating algorithm results.
- Configured serialization of each round's results to JSON under `data/outputs`.

### Changed
- Removed the `addresses` criterion from the onchain builder eligibility filter.
- Moved budget allocation settings into the `allocation` section of each algorithm config file.
- Updated amortized contract invocations to include all relevant account abstraction events.
- Simplified amortization logic so that projects receive equal credit per invocation, regardless of how many other Retro Funded projects are invoked in the same transaction.

### Fixed
- Manually linked several GitHub repositories to their corresponding NPM devtooling packages.
- Ensured distinct collections of projects per measurement period based on application submission dates.
