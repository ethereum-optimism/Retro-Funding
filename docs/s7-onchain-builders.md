# S7: Onchain Builders - Technical Details on Evaluation Methodology

This document explains the initial evaluation methodology developed for the **Retro Funding S7: Onchain Builders Mission**, including:

- **Key metrics** used to assess project impact
- **Evaluation pipeline** that transforms and aggregates metrics
- **Three initial algorithms** for assigning weights and emphasizing current vs. previous period metrics

| Algorithm         | Goal                                 | Best For                                            | Emphasis                                                         |
| ----------------- | ------------------------------------ | --------------------------------------------------- | ---------------------------------------------------------------- |
| **Superscale**    | Reward clear-cut leaders             | Large, established projects with high usage         | Adoption (favors projects with high recent activity)             |
| **Acceleratooor** | Prioritize fast-growing projects     | New and emerging projects gaining traction          | Growth (favors projects with the largest net increase in impact) |
| **Goldilocks [Used in S7]**    | Achieve a more balanced distribution | Consistently active projects with steady engagement | Retention (favors projects maintaining impact over time)         |

## Context

In 2025, Optimism's Retro Funding program is shifting to a "metrics-driven, humans-in-the-loop" approach. Instead of voting on projects, citizens vote on _algorithms_. Each algorithm represents a different strategy for rewarding projects. Algorithms will evolve in response to voting, community feedback, and new ideas over the course of the season.

This particular round—**Retro Funding S7: Onchain Builders**—focuses on protocols and dApps that are helping grow the Superchain economy. See the [round details on the Optimism governance forum](https://gov.optimism.io/t/retro-funding-onchain-builders-mission-details/9611) for more on the mission's objectives.

### Expected Impact

The overall goals for this mission include:

- Increasing network activity on the Superchain
- Attracting TVL inflows
- Driving cross-chain asset transfers and interop adoption

Because Retro Funding is _retroactive_, we place emphasis on demonstrable onchain impact—how many transactions a project was invoked in, how many users it has attracted, how much TVL it has received, and whether these metrics show meaningful retention or growth over time.

### Scope

Although topline metrics for the Superchain economy are widely available, it is harder to provide a bottom-up estimate of the onchain builder ecosystem.

Below is a rough snapshot of the economic contribution from **450+ onchain builders** that have received grants from the Optimism Foundation, including but not limited to past Retro Funding recipients.

- **300K+** active contract addresses linked to projects.
- **64M+** transactions.
- **1686 ETH+** spent in gas fees.
- **\$2.38B+** of aggregated TVL.
- **8.8M+** active addresses
- **150K+** Farcaster users (based on Farcaster IDs linked to addresses)

Note: all figures are as of January 2025, and are lower than actual figures as we have not accounted for new project sign-ups yet.

## Evaluation Methodology

### Overview

The OSO pipeline code is contained in our `OnchainBuildersCalculator` class and associated SQL models. Below is a high-level flow:

1. **Data Collection**: Gather transaction and trace-level data from the Superchain (contract invocation events, gas fees, active addresses, user labels, etc.), plus monthly TVL data from DefiLlama.
2. **Eligibility Filtering**: Exclude projects that don't meet the minimum activity thresholds (detailed below).
3. **Metric Aggregation**: Consolidate raw data per project by chain, applying amortization logic when multiple projects are invoked in the same transaction.
4. **Variant Computation**: Generate time-based _Adoption_, _Growth_, and _Retention_ metrics by comparing values across time periods.
5. **Weighting & Scoring**: Apply algorithm-specific metric and variant weightings to produce a single project score.
6. **Normalization & Ranking**: Adjust scores to ensure comparability, rank projects, and allocate funding proportionally.

### Eligibility

All projects must meet minimum activity requirements (measured over the last 180 days) to earn rewards:

1. **Transactions**: The project's contracts must be invoked in at least **1000 succesful transactions**.
2. **Active Days**: The project's contracts must be invoked on at least **10 different calendar days**.
3. **Addresses**: The project's contract must be invoked by at least **420 distinct addresses**. Note: this criterion has been removed as of M2.

DeFi projects can earn additional TVL rewards if they had at least **$1M average TVL**.

<details>
<summary>Why these thresholds?</summary>

We aim to focus on projects that have demonstrated some consistent level of real, non-bot usage on the Superchain. While these thresholds are somewhat arbitrary, they help exclude brand-new or inactive deployments that haven't yet proven traction.

</details>

<details>
<summary>Which chains are eligible?</summary>

OSO relies on the [OP Labs](https://docs.opensource.observer/docs/integrate/datasets/#superchain) for verifying project activity and computing onchain metrics. The following chains are included as of February 2025: Arena Z, Base, Ethernity, Ink, Lisk, Metal L2, Mode, OP Mainnet, RACE, Shape, Superseed, Swan Chain, Swellchain, Unichain, World Chain, Zora. Metrics should be available for projects on new chains within 30 days after mainnet launch.

</details>

<details>
<summary>How exactly are transactions counted?</summary>

Any successful transaction that invokes a project's contract as a `to` address is counted. This includes both direct contract invocations and contract invocations via traces (via `delegatecall` or `call`). The metric itself is calculated via a `count distinct` operation on the transaction hash. As of M5, we have improved contract discovery and de-duplication logic to ensure more consistent attribution of transactions to projects.

</details>

<details>
<summary>How exactly are addresses counted?</summary>

Any address that invokes a project's contract as a `from` address is counted. This includes both direct contract invocations and contract invocations via traces (via `delegatecall` or `call`). In the case of internal transactions, the `from` address is still the address that originated the transaction. The metric itself is calculated via a `count distinct` operation on all `from` addresses.

</details>

### Project-Level Metrics

Each project's score is based on five key metrics:

1. **TVL**. The average Total Value Locked (in USD) during the measurement period, focusing on ETH, stablecoins, and eventually other qualified assets.
2. **Transaction Counts**. The count of unique, successful transaction hashes that result in a state change and involve one or more of a project's contracts on the Superchain.
3. **Gas Fees**. The total L2 gas (gas consumed * gas price) for all successful transactions the results in a state change and involve one or more of a project's contracts on the Superchain.
4. **Monthly Active Users**. The count of qualified unique users (Farcaster linked addresses or World Verified Users) that initiated an event producing a state change with one or more of a project's contracts.
5. **Contract Invocations from Upgraded EOAs**. The count of contract invocations made from EIP-7702 upgraded EOAs, introduced in M5 to track adoption of account abstraction features.

These metrics are grouped by project and chain, with the potential to weight by interop- or chain-specific multipliers. Finally, we sum them across all chains to get a single aggregated value per project.

<details>
<summary>What data sources power these metrics?</summary>

- Project level metrics are derived from raw blockchain data maintained by [OP Labs](https://docs.opensource.observer/docs/integrate/datasets/#superchain)
- TVL data is maintained by [DefiLlama](https://docs.llama.fi/)
- OSO runs an [open ETL pipeline](https://docs.opensource.observer/docs/references/architecture) for transforming and aggregating these data sources into the metrics described above.

</details>

<details>
<summary>How are transactions and gas fees attributed to projects?</summary>

- If a project's contract is the `to_address` in the transaction, that project is attributed 50% of the impact.
- Any other projects whose contracts appear in the traces share the remaining 50%, split evenly.
- If no other projects appear in the traces, the `to_address` project receives 100% of the impact.
- If the `to_address` is not linked to a project in the round, but the traces include one or more known projects, then those projects together receive 50%, split evenly.

</details>

<details>
<summary>What forms of TVL do you capture?</summary>

We currently only look at "normal" TVL and ignore the value of assets held in treasuries. We don't double count assets in borrowing, staking, or vesting positions.

</details>

<details>
<summary>Do both the protocol and the asset issuer receive credit for TVL?</summary>

No. Currently the protocol (project) that holds the liquidity is attributed 100% of the average TVL. The asset issuer is, however, rewarded for network activity involving their asset.

</details>

<details>
<summary>We know addresses are not a good proxy for users. Why use them at all?</summary>

We began by only using Farcaster IDs as a proxy for more robust trusted user models. If a Farcaster ID is linked to multiple addresses, it only counts once.

As of M3, the model has been updated to use World Verified Users as well.

We are working on integrating more sophisticated models in the future.

User numbers are not heavily weighted in any of the algorithms, so this is not a major factor in the scores.

</details>

<details>
<summary>How are user ops from account abstraction projects handled?</summary>

As of M2, we have created logic specifically for handling account abstraction-related transactions, which bundle actions from multiple users into the same same transaction. UserOps are counted as a distinct transaction and smart contract wallet as a distinct address. Gas fees are shared among all projects involved in the transaction.

</details>

<details>
<summary>What are contract invocations from upgraded EOAs?</summary>

As of M5, we track contract invocations made from EIP-7702 upgraded EOAs. This metric helps identify projects that are actively supporting account abstraction features and the transition to smart contract wallets. Projects that facilitate more interactions from upgraded EOAs receive additional weight in the scoring algorithm.

</details>

### Time-Based Variants

For each core metric (i.e., transactions, gas fees, TVL, user counts), we present **three variants** for comparing the values for the current period vs. the previous period:

1. **Adoption**. The value for the current period only (e.g., the current month's transaction count). This captures the current level of adoption.
2. **Growth**. The positive difference between the current period and the previous period (e.g., net increase in TVL). Values are clipped at 0 if they decrease (no penalty for a decline, but no bonus, either).
3. **Retention**. The minimum between the current period and the previous period (e.g., how much of last month's TVL is still here). This variant rewards projects that post more consistent metrics over time.

Each algorithm we present has a different weighting of these variants. For instance, the Superscale algorithm places more emphasis on adoption (current period metrics), while the Acceleratooor algorithm places more emphasis on growth (net increases in metrics).

<details>
<summary>Show me an example</summary>

- If a project's monthly **transaction count** was 10k last month and 15k this month:

  - **Adoption** = 15k
  - **Growth** = (15k - 10k) = 5k
  - **Retention** = min(10k, 15k) = 10k

- If another project's monthly **transaction count** was 15k last month and 10k this month:
  - **Adoption** = 10k
  - **Growth** = (10k - 15k) = 0
  - **Retention** = min(15k, 10k) = 10k

Both have the same retention metric but different adoption and growth, so we can see how weighting these variants can reward different usage patterns.

</details>

### Algorithm Settings & Weights

After we assemble the metrics and compute the variants, we apply the following algorithm-specific weights:

1. **Chain Weights**

   - Potential to provide chain-specific weightings, e.g., to account for differences in project representation by chain.
   - These weights are applied before anything else, to the pre-normalized chain-level metrics by project.
   - Note: all chain activity is weighted equally in the current algorithm design.

2. **Metric Weights**

   - Each metric (e.g., `amortized_gas_fee`, `monthly_active_farcaster_users`, `monthly_average_tvl`) has a base weight.
   - Setting a weight to 0 removes that metric from consideration.

3. **Variant Weights**

   - Each variant (adoption, growth, retention) also has a base weight.
   - For example, we might put more emphasis on "growth" to reward rapidly rising projects.

These multipliers are all described in a YAML config that the pipeline reads. They can be easily tuned to reflect different philosophies on how to reward onchain projects. We encourage the community to propose different settings that reflect how we want to reward certain forms of impact.

<details>
<summary>Crosschain Multipliers: Coming Soon<sup>tm</sup></summary>

- **Purpose:** In addition to all of the above, each project can qualify for "crosschain multipliers" for supporting interoperability-related features. Starting in H2, there will be a route-specific multiplier to projects' scores based on the amount of crosschain activity they handle.
- **Application of Crosschain Multiplier**: Projects that qualify will receive a multiplier applied to their final score, increasing their potential reward.
  - Example: OP Mainnet ←→ Unichain has a 1.5X multiplier, and 30% of the project's transactions occurred between these two chains, thus the projects gets a net multiplier of (1 + 0.5 * 0.3) = 1.15X.

</details>

### Applying Weights

After we assemble the metrics and compute the variants, we min-max normalize each variant to a 0-1 scale.

Then, we multiply by the algorithm-specific weights described above:

```
normalized_variant_score = normalized_metric * metric_weight * variant_weight
```

To arrive at single project score, we take the power mean (with p=2) across all normalized variants. This somewhat penalizes "spiky" metrics and rewards a more balanced performance. Projects are not penalized for metrics for which they have null values (e.g., TVL metrics for non-defi projects).

### Finalizing & Ranking

The following steps are applied to finalize results and convert them into a reward amount:

1. **Normalize Scores**

   - Normalize all project score values so that the sum across all eligible onchain builders = 1.

2. **Reward Distribution**

   - We can optionally apply a min/max reward cap. Then each project's final score × pool size yields the reward, with amounts above or below the caps allocated to projects in the middle.
   - The reward distribution parameters are determined by the Optimism Foundation and are not algorithm-specific.

## Proposed Algorithms

We have three placeholder algorithms. Each uses the same pipeline but different YAML configurations for metrics, variants, and chain weights.

### Superscale

This algorithm aims to **reward projects with significant current usage and established impact**. It places heavier weights on the most recent values of TVL and transaction metrics, and less weight on other indicators. This strategy aims to embody the philosophy of "it's easier to agree on what _was_ useful than what _will_ be useful". You should vote for this algorithm if you want to keep things simple and give the whale projects the recognition they deserve.

<details>
<summary>Weightings & Sample Results</summary>

Weightings for Superscale:

- **Chain Weights**: Neutral. All chains are weighted equally.
- **Metric Weights**: Prefers TVL and transactions.
- **Variant Weights**: Adoption bias. Also gives a small weight to retention metrics.

Projects from Retro Funding 4 that score well include:

1. Aerodrome
2. Aave
3. Virtuals Protocol
4. Moonwell
5. Zora

</details>

### Acceleratooor

This algorithm seeks to **reward projects experiencing rapid growth** over the current measurement period. In particular, it emphasizes growth (i.e., net increases) in TVL and transaction volume. The goal is to spot breakout stars and accelerate them. This is a good algorithm to vote for if you want to create a strong signal for rising projects that the Superchain is the place to be.

<details>
<summary>Weightings & Sample Results</summary>

Weightings for Acceleratooor:

- **Chain Weights**: Neutral. All chains are weighted equally.
- **Metric Weights**: Prefers TVL and transactions.
- **Variant Weights**: Growth bias. Also gives a small weight to retention metrics.

Projects from Retro Funding 4 that score well include:

1. Aave
2. Aerodrome
3. Virtuals Protocol
4. Compound Finance
5. Paragraph

</details>

### Goldilocks [Used in S7]

This algorithm seeks to **evenly balance various aspects of impact**. It places a moderate weight on each metric and prioritizes retention over sheer growth. The goal is to support steady, sustained contributions across the board rather than "spiky" projects that only excel in one area. This is a good algorithm to vote for if you want to support a wide range of projects.

<details>
<summary>Weightings & Sample Results</summary>

Weightings for Goldilocks:

- **Chain Weights**: Neutral. All chains are weighted equally.
- **Metric Weights**: 
  - Core metrics (contract invocations: 0.20, gas fees: 0.275, TVL: 0.30)
  - User metrics (active Farcaster users: 0.0875, qualified addresses: 0.15)
  - Account abstraction (contract invocations from upgraded EOAs: 0.075)
- **Variant Weights**: Retention bias. Adoption and growth are weighted less.
- **Budget**: 1,300,000 OP (reduced from 1,333,333.33 OP in M3)
- **Percentile Cap**: 98.5 (increased from 98 in M4)

Projects from Retro Funding 4 that score well include:

1. Aerodrome
2. Zora
3. Aave
4. Layer3
5. LI.FI

</details>

## Contributing to the Model

We welcome improvements to:

1. **Data Coverage**
   - Add new domain specific data sources (e.g., account abstraction, DeFi, bridges, etc).
   - Label contracts and addresses/users.
   - Create alternate TVL calculation methodologies.
2. **Metrics and Time-Based Variants**
   - Experiment with different metrics or iterations on existing onchain metrics.
   - Propose variants that apply synthetic controls or other types of "impact over baseline" logic.
3. **Algorithmic Methods**
   - Tweak weight settings, normalization, and aggregation logic.
   - Or propose entirely new algorithms.
4. **Incentives Analysis**
   - Model attack scenarios (i.e., trying to game the algorithm) and propose defense strategies.
   - Analyze historic performance of algorithms for different cohorts of projects.

These are just a few of our ideas! All data and code can be found in the [Retro-Funding GitHub repo](https://github.com/ethereum-optimism/Retro-Funding).

## Further Resources

- [Retro Funding Algorithms Repo](https://github.com/ethereum-optimism/Retro-Funding)
- [Optimism Onchain Builders Mission Details](https://gov.optimism.io/t/retro-funding-onchain-builders-mission-details/9611)
- [DefiLlama Documentation](https://docs.llama.fi/) (for how TVL is calculated)
- [Superchain Data on BigQuery](https://docs.opensource.observer/docs/integrate/datasets/#superchain)
- [OSO Superchain S7 Metric Models](https://github.com/opensource-observer/oso/tree/main/warehouse/metrics_mesh/models/intermediate/superchain)
- [OSO's Onchain Builders Evaluation Notebook](https://app.hex.tech/00bffd76-9d33-4243-8e7e-9add359f25c7/app/067ac30b-ef55-452c-891c-cf4dff9d86c9/latest)
