# Changelog

All notable changes to algorithms, weights, and underlying OSO models will be documented here.

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
