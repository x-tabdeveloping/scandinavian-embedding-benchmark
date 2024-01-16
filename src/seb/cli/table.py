from typing import Optional

import pandas as pd
from rich.console import Console
from rich.table import Table

import seb
from seb.registries import get_all_models


def get_main_score(task: seb.TaskResult, langs: Optional[list[str]]) -> float:
    if langs is None:
        _langs = task.languages
    else:
        _langs = set(langs) & set(task.languages)
    return task.get_main_score(_langs) * 100


def open_source_to_string(open_source: bool) -> str:
    return "✓" if open_source else "✗"


def benchmark_result_to_row(
    result: seb.BenchmarkResults,
    langs: Optional[list[str]],
) -> pd.DataFrame:
    mdl_name = result.meta.name
    # sort by task name
    task_results = result.task_results
    sorted_tasks = sorted(task_results, key=lambda t: t.task_name)
    task_names = [t.task_name for t in sorted_tasks]
    scores = [get_main_score(t, langs) for t in sorted_tasks]  # type: ignore

    df = pd.DataFrame([scores], columns=task_names, index=[mdl_name])
    df["Average Score"] = result.get_main_score()  # type: ignore
    df["Open Source"] = open_source_to_string(result.meta.open_source)
    df["Embedding Size"] = result.meta.embedding_size
    return df


def convert_to_table(
    results: list[seb.BenchmarkResults],
    langs: Optional[list[str]],
) -> pd.DataFrame:
    rows = [benchmark_result_to_row(result, langs) for result in results]
    df = pd.concat(rows)
    df = df.sort_values(by="Average Score", ascending=False)
    df["Average Rank"] = compute_avg_rank(df)

    # ensure that the average and open source are the first column
    cols = df.columns.tolist()
    first_columns = [
        "Average Score",
        "Average Rank",
    ]
    other_cols = sorted(c for c in cols if c not in first_columns)
    df = df[first_columns + other_cols]
    df = df.drop(columns=["Open Source", "Embedding Size"])

    # convert name to column
    df = df.reset_index()
    df = df.rename(columns={"index": "Model"})
    ranks = [i + 1 for i in range(len(df.index))]
    df.insert(0, "Rank", ranks)) + 1)
    return df


def compute_avg_rank(df: pd.DataFrame) -> pd.Series:
    """
    For each model in the dataset, for each task, compute the rank of the model
    and then compute the average rank.
    """
    df = df.drop(columns=["Average Score", "Open Source", "Embedding Size"])

    ranks = df.rank(axis=0, ascending=False)
    avg_ranks = ranks.mean(axis=1)
    return avg_ranks


def display_model_table(result: seb.BenchmarkResults, langs: Optional[list[str]]):
    # We load the full benchmark from cache in the package
    full_bench = seb.Benchmark(languages=langs)
    models = get_all_models()
    bm_results = full_bench.evaluate_models(
        models=models,
        use_cache=True,
        run_model=False,
        cache_dir=None,
    )
    bm_results.append(result)
    result.meta.name = "NEW: " + result.meta.name
    model_name = result.meta.name
    df = convert_to_table(bm_results, langs)
    console = Console()
    table = Table(title="Benchmark Results")
    for column in df.columns:
        justify = "left" if column == "Model" else "right"
        no_wrap = column in ["Model", "Average Score", "Average Rank", "Rank"]
        table.add_column(column, justify=justify, no_wrap=no_wrap)
    model_rank = df[df["Model"] == model_name]["Rank"].iloc[0]
    models_to_display = df[(df["Rank"] <= 3) | ((df["Rank"] - model_rank).abs() < 3)]
    for _, row in models_to_display.iterrows():
        style = "deep_sky_blue1 bold" if model_name == row["Model"] else None
        rank = row["Rank"]
        values = []
        for val in row:
            if isinstance(val, float):
                val = f"{val:.2f}"
            if not isinstance(val, str):
                val = str(val)
            values.append(val)
        table.add_row(*values, style=style)
        if rank == 3:
            table.add_section()
    console.clear()
    console.print(table)
