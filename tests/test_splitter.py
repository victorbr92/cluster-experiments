from typing import Counter, List

import pandas as pd
import pytest
from cluster_experiments.random_splitter import (
    BalancedClusteredSplitter,
    ClusteredSplitter,
    StratifiedClusteredSplitter,
)


@pytest.fixture
def clusters():
    return ["cluster1", "cluster2", "cluster3", "cluster4"]


@pytest.fixture
def treatments():
    return ["A", "B"]


@pytest.fixture
def dates():
    return ["2022-01-01", "2022-01-02"]


@pytest.fixture
def df_cluster(clusters):
    return pd.DataFrame(
        {
            "cluster": clusters,
        }
    )


@pytest.fixture
def df_strata():
    return pd.DataFrame(
        {
            "cluster": [f"Cluster {i}" for i in range(100)],
            "segment": ["good"] * 50 + ["bad"] * 50,
        }
    )


@pytest.fixture
def df_strata_complete():
    return pd.DataFrame(
        {
            "cluster": [f"Cluster {i}" for i in range(100)] * 2,
            "segment": (["good"] * 50 + ["bad"] * 50) * 2,
        }
    )


@pytest.fixture
def df_strata_multiple_values():
    return pd.DataFrame(
        {
            "cluster": [f"Cluster {i}" for i in range(4)] * 2 + ["Cluster 1"],
            "segment": (["good"] * 2 + ["bad"] * 2) * 2 + ["bad"],
        }
    )


@pytest.fixture
def df_strata_two_strata_cols_two_clusters_cols():
    return pd.DataFrame(
        {
            "cluster_1": [f"City {i}" for i in range(4)] * 2,
            "cluster_2": [f"Courier {i}" for i in range(8)],
            "segment": ["good"] * 4 + ["bad"] * 4,
            "size": (["big"] * 2 + ["small"] * 2) * 2,
        }
    )


@pytest.fixture
def df_strata_different_cardinality():
    return pd.DataFrame(
        {
            "cluster": ["C1", "C2", "C3", "C4", "C5", "C6", "C6", "C6", "C6"],
            "segment": [
                "good",
                "bad",
                "good",
                "good",
                "bad",
                "good",
                "good",
                "good",
                "good",
            ],
        }
    )


@pytest.fixture
def df_switchback(clusters, dates):
    return pd.DataFrame({"cluster": sorted(clusters * 2), "date": dates * 4})


def test_clustered_splitter(clusters, treatments, df_cluster):

    splitter = ClusteredSplitter(cluster_cols=["cluster"], treatments=treatments)
    df_cluster = pd.concat([df_cluster for _ in range(100)])
    sampled_treatment = splitter.assign_treatment_df(df_cluster)
    assert len(sampled_treatment) == len(df_cluster)


def test_balanced_splitter(clusters, treatments, df_cluster):
    splitter = BalancedClusteredSplitter(clusters, treatments)
    sampled_treatment = splitter.sample_treatment(df_cluster)
    assert sorted(sampled_treatment) == ["A", "A", "B", "B"]


def test_balanced_splitter_abc(clusters, df_cluster):
    treatments = ["A", "B", "C"]
    splitter = BalancedClusteredSplitter(clusters, treatments)
    sampled_treatment = splitter.sample_treatment(df_cluster)
    assert max(Counter(sampled_treatment).values()) == 2


def test_switchback_splitter(treatments, df_switchback):
    splitter = ClusteredSplitter(
        cluster_cols=["cluster", "date"], treatments=treatments
    )
    df_switchback_large = pd.concat([df_switchback, df_switchback, df_switchback])
    assignments = splitter.assign_treatment_df(df_switchback_large)
    assert len(assignments) > 0
    assert len(assignments) == len(df_switchback_large)

    # check that each cluster has the same treatment on each date
    assert (assignments.groupby(["date", "cluster"])["treatment"].nunique() == 1).all()


def test_switchback_balanced_splitter(treatments, df_switchback):
    splitter = BalancedClusteredSplitter(
        cluster_cols=["cluster", "date"], treatments=treatments
    )

    df_switchback_large = pd.concat([df_switchback, df_switchback])
    assignments = splitter.assign_treatment_df(df_switchback_large)

    # check that each cluster has the same treatment on each date
    assert (assignments.groupby(["date", "cluster"])["treatment"].nunique() == 1).all()

    # check for treatment balance
    assert (assignments.treatment.value_counts() == 8).all()

    # all treatments are A and B
    assert set(assignments["treatment"]) == set(treatments)


def test_switchback_balanced_splitter_abc():
    df = pd.DataFrame(
        {
            "date": ["2022-01-01", "2022-01-02", "2022-01-03", "2022-01-04"],
        }
    )
    treatments = ["A", "B", "C"]
    for _ in range(100):
        splitter = BalancedClusteredSplitter(
            cluster_cols=["date"], treatments=treatments
        )
        sampled_treatment = splitter.assign_treatment_df(df)

        counts = sampled_treatment.treatment.value_counts()
        assert counts.max() == 2
        assert counts.min() == 1


def assert_balanced_strata(
    df, strata_cols: List[str], cluster_cols: List[str], treatments: List[str]
):

    splitter = StratifiedClusteredSplitter(
        strata_cols=strata_cols, cluster_cols=cluster_cols
    )

    treatment_df = splitter.assign_treatment_df(df)

    ##
    if len(cluster_cols) > 1:
        treatment_df["clusters_test"] = treatment_df[cluster_cols].agg("-".join, axis=1)
    else:
        treatment_df["clusters_test"] = treatment_df[cluster_cols]

    if len(strata_cols) > 1:
        treatment_df["strata_test"] = treatment_df[strata_cols].agg("-".join, axis=1)
    else:
        treatment_df["strata_test"] = treatment_df[strata_cols]
    ##

    for treatment in treatments:
        for stratus in treatment_df["strata_test"].unique():
            assert (
                treatment_df.query(f"strata_test == '{stratus}'")["treatment"]
                .value_counts(normalize=True)[treatment]
                .squeeze()
            ) == 1 / len(treatments)


def test_stratified(df_strata):

    # base test for balance of treatments across strata

    assert_balanced_strata(
        df_strata,
        strata_cols=["segment"],
        cluster_cols=["cluster"],
        treatments=["A", "B"],
    )


def test_stratified_shuffled_input(df_strata):

    # balance test after shuffling the order of the rows in the input dataframe

    assert_balanced_strata(
        df_strata.sample(frac=1).reset_index(drop=True),
        strata_cols=["segment"],
        cluster_cols=["cluster"],
        treatments=["A", "B"],
    )


def test_stratified_complete(df_strata_complete):

    # when we have more than 1 row per cluster in the data frame

    assert_balanced_strata(
        df_strata_complete,
        strata_cols=["segment"],
        cluster_cols=["cluster"],
        treatments=["A", "B"],
    )


def test_stratified_different_cardinality(df_strata_different_cardinality):

    # when strata are associated to different number of clusters

    assert_balanced_strata(
        df_strata_different_cardinality,
        strata_cols=["segment"],
        cluster_cols=["cluster"],
        treatments=["A", "B"],
    )


def test_stratified_two_strata_two_clusters_each_strata(
    df_strata_two_strata_cols_two_clusters_cols,
):

    # testing the balance among each strata column when more than one are provided

    splitter = StratifiedClusteredSplitter(
        strata_cols=["segment", "size"], cluster_cols=["cluster_1", "cluster_2"]
    )
    treatment_df = splitter.assign_treatment_df(
        df_strata_two_strata_cols_two_clusters_cols
    )

    for treatment in ["A", "B"]:
        for segment in ["good", "bad"]:
            assert (
                treatment_df.query(f"segment == '{segment}'")["treatment"]
                .value_counts(normalize=True)[treatment]
                .squeeze()
            ) == 0.5


def test_stratified_two_strata_two_clusters_overall_strata(
    df_strata_two_strata_cols_two_clusters_cols,
):

    # testing the balance among strata when more than one strata columns are provided

    assert_balanced_strata(
        df_strata_two_strata_cols_two_clusters_cols,
        strata_cols=["segment", "size"],
        cluster_cols=["cluster_1", "cluster_2"],
        treatments=["A", "B"],
    )


def test_stratified_strata_uniqueness(df_strata_multiple_values):

    # testing that the value error is raised when two strata have the same cluster

    splitter = StratifiedClusteredSplitter(
        strata_cols=["segment"], cluster_cols=["cluster"]
    )

    with pytest.raises(ValueError):
        splitter.assign_treatment_df(df_strata_multiple_values)
