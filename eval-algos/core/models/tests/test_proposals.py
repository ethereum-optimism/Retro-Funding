"""Unit tests for Retro Funding proposal changes (#12, #13)."""

import pandas as pd

from core.models.devtooling import (
    CREATE_FACTORY_SOURCES,
    PACKAGE_LIKE_LINK_TYPES,
    resolve_dependency_link_type,
)
from core.models.onchain_builders import OnchainBuildersCalculator, SimulationConfig


def test_create_factory_link_type():
    assert resolve_dependency_link_type("NPM") == "PACKAGE_DEPENDENCY"
    assert resolve_dependency_link_type("create_factory") == "CREATE_FACTORY_DEPENDENCY"
    assert resolve_dependency_link_type("DEPLOYMENT_FACTORY") == "CREATE_FACTORY_DEPENDENCY"
    assert "CREATE_FACTORY_DEPENDENCY" in PACKAGE_LIKE_LINK_TYPES
    assert "CREATE_FACTORY" in CREATE_FACTORY_SOURCES


def test_user_metric_blend_injects_composite_metric():
    raw = pd.DataFrame(
        [
            {
                "project_id": "p1",
                "project_name": "Demo",
                "display_name": "Demo",
                "chain": "base",
                "measurement_period": "Aug 2025",
                "metric_name": "farcaster_users",
                "amount": 100.0,
                "is_eligible": True,
            },
            {
                "project_id": "p1",
                "project_name": "Demo",
                "display_name": "Demo",
                "chain": "base",
                "measurement_period": "Aug 2025",
                "metric_name": "kyc_verified_users",
                "amount": 50.0,
                "is_eligible": True,
            },
        ]
    )
    config = SimulationConfig(
        periods={"current": "Aug 2025", "previous": "Jul 2025"},
        chains={"base": 1.0},
        metrics={"diversified_user_activity": 1.0},
        metric_variants={"adoption": 1.0},
        user_metric_blend={
            "diversified_user_activity": {
                "farcaster_users": 0.5,
                "kyc_verified_users": 0.5,
            }
        },
    )
    calc = OnchainBuildersCalculator(config)
    calc.run_analysis(raw)
    blended = calc.analysis["raw_data"]
    composite = blended[blended["metric_name"] == "diversified_user_activity"]
    assert len(composite) == 1
    assert composite.iloc[0]["amount"] == 75.0
