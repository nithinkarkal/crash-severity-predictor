"""
training entrypoint
"""

import os

import mlflow

from common.utils.mlflow import (
    log_run,
    promote_if_better,
    register_model,
    setup_mlflow,
)
from common.utils.paths import (
    METRIC_DIR,
    MODEL_CONFIG,
    MODEL_DIR,
    PROCESSED_DATA_DIR,
    REPORT_DIR,
)
from services.training.src.evaluate_model import run_evaluation
from services.training.src.train_model import run_training


def main() -> None:

    setup_mlflow()

    with mlflow.start_run():
        train_out = run_training(
            processed_data_dir=PROCESSED_DATA_DIR,
            model_out_dir=MODEL_DIR,
            reports_dir=REPORT_DIR,
            model_name=MODEL_CONFIG["model_name"],
            model_parameters=MODEL_CONFIG["model_parameters"],
            top_n_features=MODEL_CONFIG["top_n_features"],
        )

        # eval is used here for docker entrypoint
        eval_out = run_evaluation(
            model_name=MODEL_CONFIG["model_name"],
            processed_data_dir=PROCESSED_DATA_DIR,
            model_dir=MODEL_DIR,
            metrics_dir=METRIC_DIR,
            reports_dir=REPORT_DIR,
        )

        # mlflow: log run -> register the trained model as a new candidate version.
        model_info = log_run(
            train_out=train_out,
            eval_out=eval_out,
        )
        registered_version = register_model(
            model_info=model_info,
            registry_model_name=MODEL_CONFIG["model_registry_name"],
        )

        # Promotion to production is governed by the `asp_retraining` Airflow DAG
        # (Option B): it runs compare (STEP 5) then promote (STEP 6) as explicit
        # steps via `services.training.promote`. So training does NOT auto-promote
        # by default. Set ASP_PROMOTE_AFTER_TRAIN=1 to also promote straight from
        # training (e.g. if the backend `/train` path wants a self-contained flow).
        if os.environ.get("ASP_PROMOTE_AFTER_TRAIN", "0") == "1":
            promote_if_better(
                registered_version=registered_version,
                eval_out=eval_out,
                registry_model_name=MODEL_CONFIG["model_registry_name"],
            )


if __name__ == "__main__":
    main()
