# Diversified user metrics beyond Farcaster (Retro Funding #13)

Adds optional **user metric blending** so eval configs can combine Farcaster counts with KYC, CEX-linked, and heuristic onchain activity signals.

## Config

```yaml
simulation:
  user_metric_blend:
    diversified_user_activity:
      farcaster_users: 0.35
      kyc_verified_users: 0.25
      cex_linked_active_users: 0.20
      non_kyc_active_users: 0.20
  metrics:
    diversified_user_activity: 0.175
    contract_invocations: 0.35
    layer2_gas_fees_amortized: 0.35
    defillama_tvl: 0.0
    worldchain_users_aggregation: 0.125
    active_addresses_aggregation: 0.0
```

The calculator synthesizes `diversified_user_activity` rows before pivoting metrics, enabling gradual de-emphasis of any single onboarding rail.

## Example proposal weights

See `results/S7/community_submissions/onchain-diversified-users/weights/onchain__goldilocks_diversified_users.yaml`.

Closes #13
