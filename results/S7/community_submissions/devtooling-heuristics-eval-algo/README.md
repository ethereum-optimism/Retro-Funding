 # DevTooling Heuristics Evaluation Algorithm

This is a community submission for the Retro Funding project. The algorithm uses heuristics to evaluate and rank projects based on various metrics.

## Original Author
- GitHub: [@theChriscen](https://github.com/theChriscen)

## Documentation
Original documentation [here](https://docs.google.com/document/d/1rKerUpIO1q3SDT3-4JaUrf7k_n1rgSc0Gl6f0DLiaCs/edit?usp=sharing)

---

**Comparative Analysis Report: Heuristics vs. OpenRank Rankings for Devtooling Projects in Retro Funding**

**Introduction**

This report compares two ranking systems for developer tooling projects: the domain \- heuristics ranking system and the Openrank system. By leveraging provided ranking data and YAML configuration files, we analyze how these systems evaluate projects and their implications for Retro Funding, a mechanism aimed at allocating resources to projects actively advancing the blockchain developer ecosystem, particularly within the Optimism network. The analysis uses a Spearman correlation coefficient of 0.8195 and rank comparison data for the top 20 heuristics-ranked projects to highlight similarities, differences, and how the heuristics system enhances Retro Funding’s objectives.

**Data Overview**

**Ranking Correlation**

The Spearman correlation coefficient between the heuristics and OpenRank rankings is **0.8195**, with a p-value of **0.0000**. This indicates a **strong positive correlation** that is statistically significant (p \< 0.05), suggesting substantial agreement in the relative ordering of projects. However, notable rank differences for specific projects reveal distinct methodological priorities, which we explore through the YAML configurations.

**Top 20 Heuristics-Ranked Projects with OpenRank Comparison**

The table below lists the top 20 projects by heuristics rank, their OpenRank positions, and rank differences (heuristics\_rank \- openrank\_rank):

| Display Name | Heuristics Rank | OpenRank Rank | Rank Difference |
| :---- | :---- | :---- | :---- |
| DefiLlama | 1 | 7 | \-6 |
| OpenZeppelin Contracts | 2 | 2 | 0 |
| Cannon | 3 | 27 | \-24 |
| Ethers.js | 4 | 1 | 3 |
| Solidity | 5 | 3 | 2 |
| Viem | 6 | 4 | 2 |
| Hardhat | 7 | 5 | 2 |
| Wagmi | 8 | 6 | 2 |
| Snapshot | 9 | 44 | \-35 |
| Vyper | 10 | 37 | \-27 |
| web3.py | 11 | 12 | \-1 |
| Slither | 12 | 22 | \-10 |
| Solady | 13 | 10 | 3 |
| Ronan Sandford | 14 | 11 | 3 |
| MerkleTreeJS | 15 | 29 | \-14 |
| Scaffold-ETH 2 | 16 | 13 | 3 |
| Titanoboa | 17 | 43 | \-26 |
| Blockscout  | 18 | 32 | \-14 |
| rotki | 19 | 35 | \-16 |
| IPFS | 20 | 14 | 6 |

**Methodology and Metrics Comparison**

**Heuristics System**

The heuristics system uses a weighted sum of metrics, as defined in its YAML configuration:

`yaml`

`weights:`  
  `stars: 0.1`  
  `forks: 0.1`  
  `contributors: 0.1`  
  `dependents: 0.20`  
  `commit_volume: 0.2`  
  `pull_requests: 0.2`  
  `forks_to_import_ratio: 0.1`  
`thresholds:`  
  `min_dependents: 1`  
  `min_contributors: 1`

* **Metrics**:  
  * **Popularity**: `stars` (0.1), `forks` (0.1).  
  * **Community**: `contributors` (0.1).  
  * **Ecosystem Impact**: `dependents` (0.2).  
  * **Development Activity**: `commit_volume` (0.2), `pull_requests` (0.2).  
  * **Derived Metric**: `forks_to_import_ratio` (0.1), calculated as forks divided by unique committers plus one, capturing community engagement relative to contributor activity.  
* **Characteristics**: Simple, transparent, and focused on recent development activity (40% weight) and ecosystem relevance (20% on dependents). It excludes onchain metrics, relying on GitHub and dependency data.  
* **Eligibility**: Requires at least one dependent project and one contributor.

**OpenRank System**

The OpenRank system, detailed in its YAML, employs a more complex, graph-based approach:

`yaml`

`devtooling_project_pretrust_weights:`  
  `star_count: 0.3`  
  `fork_count: 0.3`  
  `num_packages_in_deps_dev: 0.4`  
`onchain_project_pretrust_weights:`  
  `total_transaction_count: 0.4`  
  `total_gas_fees: 0.4`  
  `total_active_addresses: 0.2`  
`event_type_weights:`  
  `commit_code: 1.0`  
  `starred: 1.0`  
  `forked: 1.0`  
  `pull_request_opened: 1.0`  
`utility_weights:`  
  `'Language & Compilation Tools': 5.00`  
  `'Core Protocol Interfaces': 4.00`

* **Metrics**:  
  * **Devtooling Projects**: `star_count` (0.3), `fork_count` (0.3), `num_packages_in_deps_dev` (0.4).  
  * **Onchain Projects**: Transaction count (0.4), gas fees (0.4), active addresses (0.2).  
  * **Events**: Equal weighting (1.0) for commits, stars, forks, and pull request openings.  
  * **Utility Weights**: Category-specific multipliers (e.g., 5.0 for compilers, 1.0 for niche tools).  
* **Characteristics**: Balances popularity and ecosystem impact, with adjustments for project category and onchain activity. It uses graph-based trust propagation with time decays and link weights.  
* **Eligibility**: Requires at least three package links and five onchain developer links.

**Key Methodological Differences**

* **Metric Emphasis**:  
  * **Heuristics**: Prioritizes development activity (40% on `commit_volume` and `pull_requests`) and ecosystem impact (`dependents`, 20%). Popularity metrics (`stars`, `forks`) have lower weight (20% total).  
  * **OpenRank**: For devtooling, balances popularity (`star_count`, `fork_count`, 60% total) with dependencies (40%). Onchain metrics dominate for blockchain projects, adding a usage dimension absent in heuristics.  
* **Complexity and Adjustments**:  
  * **Heuristics**: Uses a straightforward weighted sum, ensuring transparency and predictability.  
  * **OpenRank**: Employs a graph-based model with time decays, link weights, and category multipliers, adding complexity and potential bias toward predefined categories.  
* **Category Sensitivity**:  
  * **Heuristics**: Treats all projects equally, regardless of type, focusing on raw metrics.  
  * **OpenRank**: Boosts scores for categories like "Language & Compilation Tools" (5.0x), potentially elevating projects like Solidity over equally active but less prioritized ones.  
* **Data Scope**:  
  * **Heuristics**: Relies on off-chain data (GitHub, dependencies), ignoring blockchain activity.  
  * **OpenRank**: Integrates onchain metrics, favoring projects with high transaction volumes or gas fees.  
* **Derived Metrics**:  
  * **Heuristics**: Includes `forks_to_import_ratio`, capturing community engagement relative to contributor activity, a signal Openrank lacks.  
  * **OpenRank**: No equivalent derived metric, relying on raw counts and category adjustments.

**Analysis of Ranking Results**

**Spearman Correlation**

The Spearman correlation of **0.8195** (p-value: 0.0000) indicates a strong, statistically significant agreement between the two systems. This suggests that both systems generally rank projects similarly, reflecting shared priorities in assessing project importance. However, specific deviations highlight their differing focuses, as seen in the rank differences for the top 20 heuristics-ranked projects.

![image](https://github.com/user-attachments/assets/f0ed7ab2-c103-4fb7-ae85-e72f546c3892)

**Notable Rank Differences**

* **Snapshot**: 9th in heuristics, 44th in OpenRank (-35). Snapshot’s high heuristics rank likely stems from strong `commit_volume`, `pull_requests`, or `dependents`, reflecting active development or governance ecosystem reliance. OpenRank’s lower rank may result from modest popularity metrics or a non-prioritized category (e.g., "Others", 1.0 weight).  
* **Vyper**: 10th in heuristics, 37th in OpenRank (-27). As a smart contract language, Vyper’s recent activity (`commit_volume`, `pull_requests`) boosts its heuristics score, while OpenRank’s emphasis on stars and category weights (possibly lower for Vyper) reduces its rank.  
* **Cannon**: 3rd in heuristics, 27th in OpenRank (-24). Cannon’s high heuristics rank suggests significant recent activity or ecosystem impact, undervalued by OpenRank’s popularity focus or lack of category boost.  
* **Ethers.js**: 4th in heuristics, 1st in OpenRank (+3). Ethers.js, a mature library, benefits from high `star_count` and `fork_count` in OpenRank, but its slightly lower heuristics rank may indicate reduced recent activity compared to projects like DefiLlama.  
* **OpenZeppelin Contracts**: 2nd in both systems (0). Strong agreement reflects balanced performance across popularity, activity, and ecosystem impact metrics in both systems.

**Reasons for Deviations**

The YAML configurations explain these differences:

* **Activity Focus**: Heuristics’ heavy weighting of `commit_volume` and `pull_requests` (40% combined) elevates projects with recent development, like Snapshot and Vyper, over those with stable but less active repositories (e.g., Ethers.js).  
* **Ecosystem Impact**: Heuristics’ `dependents` (0.2) and `forks_to_import_ratio` (0.1) prioritize projects critical to the ecosystem components or with engaged communities, boosting tools like Cannon.  
* **Popularity Bias**: OpenRank’s higher weights on `star_count` and `fork_count` (0.6 total) favor established projects, explaining Ethers.js’s top rank.  
* **Category Adjustments**: OpenRank’s utility weights (e.g., 5.0 for "Language & Compilation Tools") amplify scores for projects like Solidity, potentially overshadowing rankings for projects in less favored categories.  
* **Onchain Metrics**: OpenRank’s inclusion of onchain data (e.g., transaction counts) may influence rankings for projects with blockchain components, a factor heuristics ignores.

**Implications for Retro Funding**

Retro Funding aims to allocate resources to projects actively advancing the developer tooling ecosystem, particularly within the Optimism network. The heuristics system aligns closely with this goal through several advantages:

* **Prioritization of Active Development**:  
  * By assigning 40% weight to `commit_volume` and `pull_requests`, heuristics identifies projects with ongoing innovation, such as ensuring funding supports tools currently enhancing the ecosystem. For example, Snapshot’s high rank (9th) reflects active governance contributions, critical for Optimism’s community-driven model.  
* **Ecosystem Relevance**:  
  * The 20% weight on `dependents` highlights projects with significant downstream impact, such as Cannon, which may be integral to deployment workflows despite lower OpenRank visibility.  
* **Community Engagement**:  
  * The `forks_to_import_ratio` metric captures projects with active community customization, supporting tools that foster collaboration and adoption within Optimism.  
* **Transparency and Simplicity**:  
  * The straightforward weighted sum approach ensures clear, predictable funding decisions, enhancing trust among developers and stakeholders.

In contrast, OpenRank’s strengths lie in recognizing established projects and those with strategic category importance or high blockchain usage. However, its complexity and reliance on onchain metrics may:

* **Overemphasize Popularity**: Projects like Ethers.js rank higher due to stars, potentially diverting funds from more active but less recognized tools.  
* **Category Bias**: Utility weights favor compilers (e.g., Solidity), which may not align with Retro Funding’s goal of supporting diverse, active contributions across all tooling categories.  
* **Onchain Focus**: While relevant for blockchain projects, onchain metrics may skew rankings away from pure devtooling contributions critical to Optimism’s ecosystem.

**Specific Improvements for Retro Funding**

* **Dynamic Allocation**: Heuristics’ activity focus ensures funding prioritizes projects driving current innovation, fostering a responsive ecosystem.  
* **Inclusivity**: By ignoring category biases, heuristics supports niche but active projects (e.g., Snapshot, Titanoboa), broadening the funding net.  
* **Alignment with Optimism’s Goals**: Emphasizing development activity aligns with Optimism’s aim to enhance developer tools, directly benefiting its Layer 2 scaling solutions.

**Conclusion**

The heuristics and Openrank systems exhibit strong alignment (Spearman correlation: 0.8195), yet their differences are pivotal for Retro Funding. The heuristics system’s emphasis on recent activity, ecosystem impact, and community engagement makes it ideally suited to identify and fund projects actively shaping the Optimism developer ecosystem. OpenRank, while valuable for recognizing established or blockchain-active projects, may undervalue emerging or niche tools due to its popularity bias and category adjustments. By adopting the heuristics ranking, Retro Funding can ensure transparent, inclusive, and effective resource allocation, driving innovation and growth within the Optimism ecosystem.  
