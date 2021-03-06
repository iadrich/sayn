from itertools import product
import os

import pytest
from ruamel.yaml import YAML


def get_dbs():
    """Get a list of database configurations from environment variables"""
    dbs = [
        (k[len("TEST_DB_") :], YAML().load(v))
        for k, v in os.environ.items()
        if k.startswith("TEST_DB_")
    ]

    if len(dbs) == 0:
        dbs = [("sqlite", {"type": "sqlite", "database": ":memory:"})]

    return dbs


ALL_DBS = get_dbs()


def pytest_configure(config):
    """Register the dbs marker that allows for test skipping"""
    config.addinivalue_line(
        "markers", "source_dbs(list): List of dbs supported for source"
    )
    config.addinivalue_line(
        "markers", "target_dbs(list): List of dbs supported for target"
    )


@pytest.fixture
def skip_test():
    """Trick to skip specific tests"""
    pytest.skip("No DB type supported by this test")


def pytest_generate_tests(metafunc):
    """Dynamically generates tests based on parameters.

    Currently, for tests that use databases, this generates 2 fixtures: source_db and target_db.
    Including these parameters in a test trigger this dynamic generation.
    Defaults to sqlite in memory databases.
    """

    if "source_db" in metafunc.fixturenames:
        source_db_filter = [
            db
            for m in metafunc.definition.own_markers
            if m.name == "source_dbs"
            for db in m.args[0]
        ]

        if len(source_db_filter) > 0:
            source_dbs = [v for v in ALL_DBS if v[1]["type"] in source_db_filter]
        else:
            source_dbs = ALL_DBS

    if "target_db" in metafunc.fixturenames:
        target_db_filter = [
            db
            for m in metafunc.definition.own_markers
            if m.name == "target_dbs"
            for db in m.args[0]
        ]

        if len(target_db_filter) > 0:
            target_dbs = [v for v in ALL_DBS if v[1]["type"] in target_db_filter]
        else:
            target_dbs = ALL_DBS

    if "target_db" in metafunc.fixturenames and "source_db" in metafunc.fixturenames:
        db_pairs = list(product(source_dbs, target_dbs))
        if len(db_pairs) == 0:
            metafunc.fixturenames.insert(0, "skip_test")
        else:
            metafunc.parametrize(
                "source_db,target_db",
                [(c[0][1], c[1][1]) for c in db_pairs],
                ids=[f"src:{c[0][0]},dst:{c[1][0]}" for c in db_pairs],
            )
    elif "target_db" in metafunc.fixturenames:
        if len(target_dbs) == 0:
            metafunc.fixturenames.insert(0, "skip_test")
        else:
            metafunc.parametrize(
                "target_db", [d[1] for d in target_dbs], ids=[d[0] for d in target_dbs]
            )
