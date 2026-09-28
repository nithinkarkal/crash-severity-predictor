# Setup and usage guide

We use [DagsHub's MLflow tracking server integration](https://dagshub.com/docs/integration_guide/mlflow_tracking/).

In order to authorize the client, we need a `DAGSHUB_USER_TOKEN`.

During development the recommended practice is that each team member generates a personal token. To do so follow these steps:

1. Go to [dagshub.com/user/settings/tokens](https://dagshub.com/user/settings/tokens)
2. At **Manage Personal Access Tokens** click on `Generate New Token`, name it, click on `Generate Token`, then copy the generated token.
3. Now at the local project root, open `.env` and add `DAGSHUB_USER_TOKEN=<paste_token_here>`

---

Later the recommended approach is to have a **dedicated service account** on DagsHub with a **dedicated project token**. This token will then be stored as a secret in:

- Docker Compose,
- Kubernetes Secrets,
- GitHub Actions Secrets,
- or wherever we need it...
