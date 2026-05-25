# Deployment factory dependencies (Retro Funding #12)

Extends the devtooling dependency graph to treat **create-factory** deployment links as first-class dependencies alongside npm/pip/go package links.

## Changes

- `resolve_dependency_link_type()` maps `CREATE_FACTORY`, `DEPLOYMENT_FACTORY`, and related sources to `CREATE_FACTORY_DEPENDENCY`.
- Factory links participate in the same EigenTrust pass as package dependencies (time decay + utility weights configurable via YAML).

## Example weight config

```yaml
simulation:
  link_type_time_decays:
    package_dependency: 1.0
    create_factory_dependency: 0.90
  link_type_weights:
    package_dependency: 1.0
    create_factory_dependency: 1.5
  event_type_weights:
    create_factory: 1.0
    deployment_factory: 1.0
```

## Data expectation

`devtooling__dependency_graph.csv` rows with `dependency_source` set to `CREATE_FACTORY` or `DEPLOYMENT_FACTORY` are ingested at contract-verification time and weighted in the graph.

Closes #12
