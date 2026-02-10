import json
import os
import subprocess
import sys
import warnings
from typing import Any, Dict, Optional, Tuple, Union

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

warnings.filterwarnings("ignore")

import pandas as pd
from openai import AzureOpenAI, OpenAI

from judge import Judge, ScoringPoint
from tester import Tester
from utils import check_package_version, load_task_case

from taskweaver.app.app import TaskWeaverApp
from taskweaver.llm import LLMApi


def _make_app_key(app_dir: str, config_var: Optional[Dict]) -> str:
    """Create a hashable key for caching TaskWeaverApp instances."""
    normalized_dir = os.path.abspath(app_dir)
    config_str = json.dumps(config_var or {}, sort_keys=True)
    return f"{normalized_dir}|{config_str}"


def _get_llm_client(app: TaskWeaverApp) -> Tuple[Union[OpenAI, AzureOpenAI], str]:
    """Extract the LLM client and model name from a TaskWeaverApp."""
    llm_api = app.app_injector.get(LLMApi)
    service = llm_api.completion_service
    return service.client, service.config.model


def auto_evaluate(
    eval_case_dir: str,
    app: Optional[TaskWeaverApp] = None,
    llm_client: Optional[Union[OpenAI, AzureOpenAI]] = None,
    model_name: Optional[str] = None,
) -> Tuple[float, float]:
    """Run a single evaluation case.

    Args:
        eval_case_dir: Path to the case directory.
        app: Optional pre-created TaskWeaverApp to reuse (avoids re-auth).
        llm_client: Optional shared LLM client for tester/judge calls.
        model_name: Optional model name for the shared LLM client.
    """
    case = load_task_case(eval_case_dir)

    app_dir = case["app_dir"]
    config_var = case.get("config_var", None)
    task_description = case["task_description"]
    dependencies = case.get("dependencies", [])
    data_files = case.get("data_files", [])
    pre_command = case.get("pre_command", [])
    max_rounds = case.get("max_rounds", 10)

    for dep in dependencies:
        check_package_version(dep)

    for command in pre_command:
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode == 0:
            print(f"Pre-command executed successfully: {command}")
            print(result.stdout)
        else:
            print(f"Pre-command failed: {command}")
            print(result.stdout)

    upload_files = []
    for data_file in data_files:
        src = os.path.join(eval_case_dir, data_file)
        if not os.path.exists(src):
            raise FileNotFoundError(f"Data file {data_file} not found in {eval_case_dir}")
        if os.path.isfile(src):
            upload_files.append({"name": os.path.basename(data_file), "path": src})
        else:
            for root, _dirs, files in os.walk(src):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, os.path.dirname(src))
                    upload_files.append({"name": rel, "path": fpath})

    tester = Tester(
        task_description=task_description,
        app_dir=app_dir,
        config_var=config_var,
        max_rounds=max_rounds,
        app=app,
        llm_client=llm_client,
        model_name=model_name,
        files=upload_files if upload_files else None,
    )

    conversation = tester.run()

    judge_client = llm_client or tester.llm_client
    judge_model = model_name or tester.model_name
    judge = Judge(judge_client, judge_model)
    scoring_points = [
        ScoringPoint(score_point=sp["score_point"], weight=sp["weight"])
        for sp in case["scoring_points"]
    ]
    score, normalized_score, results = judge.evaluate(
        task_description,
        conversation,
        scoring_points,
    )

    tester.close()

    max_score = sum(sp.weight for sp in scoring_points)
    print(f"\nFinal Score: {score}/{max_score} (normalized: {normalized_score:.2%})")

    return score, normalized_score


def batch_auto_evaluate(
    result_file_path: str,
    eval_case_root: str,
    flush_result_file: bool = False,
    sleep_time: int = 0,
):
    """Run all evaluation cases in a directory.

    Creates and caches TaskWeaverApp instances by (app_dir, config_var) so that
    authentication only happens once per unique configuration.
    """
    if not os.path.exists(result_file_path):
        df = pd.DataFrame(columns=["case_file", "score", "normalized_score"])
        df.to_csv(result_file_path, index=False)

    results = pd.read_csv(result_file_path, dtype={"case_file": str})
    evaluated_case_files = [str(f) for f in results["case_file"].tolist()]
    if flush_result_file:
        evaluated_case_files = []
    print(f"Evaluated case files: {evaluated_case_files}")
    eval_config_dirs = os.listdir(eval_case_root)
    print(f"Eval config dirs: {eval_config_dirs}")

    app_cache: Dict[str, TaskWeaverApp] = {}
    shared_llm_api: Optional[Any] = None
    shared_llm_client: Optional[Union[OpenAI, AzureOpenAI]] = None
    shared_model_name: Optional[str] = None

    try:
        for eval_case_dir in eval_config_dirs:
            if eval_case_dir in evaluated_case_files:
                print(f"Skip {eval_case_dir} because it has been evaluated.")
                continue
            print("------------ Start evaluating ------------", eval_case_dir)
            eval_case_dir_path = os.path.join(eval_case_root, eval_case_dir)

            try:
                # Load case to determine app config for caching
                case = load_task_case(eval_case_dir_path)
                app_dir = case["app_dir"]
                config_var = case.get("config_var", None)
                app_key = _make_app_key(app_dir, config_var)

                if app_key not in app_cache:
                    print(f"Creating app for config: {app_key}")
                    app_cache[app_key] = TaskWeaverApp(
                        app_dir=app_dir,
                        config=config_var,
                        llm_api=shared_llm_api,
                    )

                app = app_cache[app_key]

                # Extract shared LLM API and client from first app (auth happens once)
                if shared_llm_api is None:
                    shared_llm_api = app.app_injector.get(LLMApi)
                    shared_llm_client, shared_model_name = _get_llm_client(app)

                score, normalized_score = auto_evaluate(
                    eval_case_dir_path,
                    app=app,
                    llm_client=shared_llm_client,
                    model_name=shared_model_name,
                )
            except Exception as e:
                print(f"Error evaluating {eval_case_dir}: {e}")
                score, normalized_score = 0, 0

            new_res_row = pd.DataFrame(
                {
                    "case_file": [eval_case_dir],
                    "score": [score],
                    "normalized_score": [normalized_score],
                },
            )
            results = pd.concat([results, new_res_row], ignore_index=True)

            print("------------ Finished evaluating ------------", eval_case_dir)

            results.to_csv(result_file_path, index=False)

            if sleep_time > 0:
                print(f"Sleeping for {sleep_time} seconds...")
                import time

                time.sleep(sleep_time)
    finally:
        # Clean up all cached apps
        for app in app_cache.values():
            try:
                app.stop()
            except Exception:
                pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TaskWeaver auto evaluation script")
    parser.add_argument(
        "-m",
        "--mode",
        choices=["single", "batch"],
        required=True,
        help="Evaluation mode: single case or batch of cases",
    )
    parser.add_argument(
        "-p",
        "--path",
        type=str,
        required=True,
        help="Path to the evaluation case directory (single) or parent directory (batch)",
    )
    parser.add_argument(
        "-r",
        "--result",
        type=str,
        default="sample_case_results.csv",
        help="Path to the result CSV file (batch mode only)",
    )
    parser.add_argument(
        "-f",
        "--fresh",
        action="store_true",
        help="Re-evaluate all cases, ignoring previous results",
    )
    parser.add_argument(
        "-s",
        "--sleep",
        type=int,
        default=0,
        help="Sleep time in seconds between evaluations (batch mode)",
    )

    args = parser.parse_args()

    if args.mode == "single":
        score, normalized_score = auto_evaluate(args.path)
        print(f"Score: {score}, Normalized score: {normalized_score}")
    elif args.mode == "batch":
        batch_auto_evaluate(
            args.result,
            args.path,
            flush_result_file=args.fresh,
            sleep_time=args.sleep,
        )
