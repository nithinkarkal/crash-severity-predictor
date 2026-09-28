# ASP References

This document lists the main technical, scientific, and official documentation sources consulted during the development of the Accident Severity Predictor (ASP) capstone project.

---

## Python

* **Python `subprocess`**
  https://docs.python.org/3/library/subprocess.html

* **Python `unittest.mock`**
  https://docs.python.org/3/library/unittest.mock.html

* **pytest fixtures**
  https://docs.pytest.org/en/stable/reference/fixtures.html

* **pytest `tmp_path` fixture**
  https://docs.pytest.org/en/stable/how-to/tmp_path.html

* **pytest `autouse` fixtures**
  https://docs.pytest.org/en/stable/how-to/fixtures.html

* **pytest `conftest.py` / sharing fixtures**
  https://stackoverflow.com/questions/33654052/how-to-share-object-from-fixture-to-all-tests-using-pytest

* **FastAPI testing with pytest**
  https://fastapi.tiangolo.com/tutorial/testing/

* **Requests documentation**
  https://requests.readthedocs.io/en/latest/user/quickstart/

---

## FastAPI & Pydantic

* **FastAPI background tasks**
  https://fastapi.tiangolo.com/tutorial/background-tasks/

* **FastAPI error handling**
  https://fastapi.tiangolo.com/tutorial/handling-errors/

* **Pydantic fields**
  https://docs.pydantic.dev/latest/concepts/fields/

* **Pydantic models**
  https://docs.pydantic.dev/latest/concepts/models/

* **Pydantic Settings**
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/

---

## Docker

* **Docker CLI reference**
  https://docs.docker.com/reference/cli/docker/

* **Docker volumes**
  https://docs.docker.com/engine/storage/volumes/

* **Docker networking**
  https://docs.docker.com/engine/network/

* **Docker security — Docker daemon attack surface**
  https://docs.docker.com/engine/security/

* **Protect access to the Docker daemon**
  https://docs.docker.com/engine/security/protect-access/

* **Docker build best practices**
  https://docs.docker.com/build/building/best-practices/

* **Running containers as a non-root user**
  https://docs.docker.com/build/building/best-practices/#user

* **Docker with Python**
  https://docs.docker.com/guides/python/

* **Controlling Docker containers from another container**
  https://medium.com/@smrati.katiyar/controlling-docker-containers-on-host-from-another-docker-container-on-same-host-aa5998c8515c

* **Docker SDK vs. Python subprocess**
  https://stackoverflow.com/questions/74118698/calling-a-docker-container-through-python-subprocess

---

## Docker Compose

* **Compose volumes**
  https://docs.docker.com/reference/compose-file/volumes/

* **Compose profiles**
  https://docs.docker.com/compose/how-tos/profiles/

---

## Code Quality & Development Tools

### Pre-commit

* **Pre-commit documentation**
  https://pre-commit.com/

* **Pre-commit configuration example**
  https://github.com/pre-commit/pre-commit/blob/main/.pre-commit-config.yaml

### MyPy

* **MyPy documentation**
  https://mypy.readthedocs.io/en/stable/

* **Typeshed issue related to Base64 / ASCII typing**
  https://github.com/python/typeshed/issues/3145

### Ruff

* **Ruff documentation**
  https://docs.astral.sh/ruff/

---

## DagsHub, DVC & MLflow

### DagsHub

* **DagsHub documentation**
  https://dagshub.com/docs/

* **DagsHub DVC integration**
  https://dagshub.com/docs/integration_guide/dvc/

* **DagsHub Storage**
  https://dagshub.com/docs/feature_guide/dagshub_storage/

### AWS / Boto3

* **Boto3 configuration**
  https://docs.aws.amazon.com/boto3/latest/guide/configuration.html

### MLflow

* **MLflow Python API — data**
  https://mlflow.org/docs/latest/api_reference/python_api/mlflow.data.html

* **MLflow Python API — client**
  https://mlflow.org/docs/latest/api_reference/python_api/mlflow.client.html

---

## GitHub Actions

* **GitHub Actions — secrets**
  https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets

---

## Streamlit

* **Streamlit page configuration (`st.set_page_config`)**
  https://docs.streamlit.io/develop/api-reference/configuration/st.set_page_config

* **Streamlit multipage applications / Session State architecture**
  https://docs.streamlit.io/develop/concepts/multipage-apps

* **Streamlit Session State**
  https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state

* **Streamlit HTML rendering (`st.html`)**
  https://docs.streamlit.io/develop/api-reference/text/st.html

* **Streamlit `.gitignore` example**
  https://github.com/streamlit/streamlit/blob/develop/.gitignore

* **Streamlit CSS / frontend example**
  https://github.com/crewAIInc/template_frontend_crewai_flows_streamlit_ui/blob/main/app.py

---

## Plotly

* **Plotly Indicator graph object**
  https://plotly.com/python-api-reference/generated/plotly.graph_objects.Indicator.html

* **Plotly gauge charts**
  https://plotly.com/python/gauge-charts/

---

## BAAC — French Road Accident Data

* **ONISR — Description des bases de données annuelles BAAC**
  https://www.onisr.securite-routiere.gouv.fr/sites/default/files/2024-10/Description%20des%20bases%20de%20donn%C3%A9es%20annuelles.pdf

The BAAC (Bulletin d'Analyse des Accidents Corporels) documentation was used as the reference for understanding the structure and meaning of the accident datasets and their variables.

---

## Project-Specific References

The sources listed above were consulted for implementation decisions involving:

* Python process execution and testing
* FastAPI APIs and background processing
* Pydantic validation and configuration
* Docker and Docker Compose
* Container security and inter-container communication
* Streamlit frontend architecture and state management
* Plotly visualizations
* MLflow experiment tracking
* DVC and DagsHub data/model versioning
* GitHub Actions CI/CD
* MyPy and Ruff static analysis
* pytest and test fixtures
* French BAAC accident data and variable definitions
