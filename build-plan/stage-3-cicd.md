# Stage 3 – CI/CD Pipeline

## Goal
Introduce automated verification and deployment so every change is tested, packaged, and promoted consistently.

## Plan
1. **Select runner + triggers**
   - Use GitHub Actions (or repo-native equivalent) with workflows for `push`/`pull_request` and a tagged release deploy job.
2. **Define jobs**
   - `lint-and-test`: set up Python 3.11, install `requirements.txt`, run formatter/lint (ruff/flake8) and `pytest`.
   - `build-artifact`: on success, build Docker image tagged with commit SHA, push to registry if credentials present.
3. **Secrets & caching**
   - Document required secrets (e.g., `REGISTRY_USER`, `REGISTRY_TOKEN`, optional `DEPLOY_SSH_KEY`).
   - Add pip cache + docker layer caching to speed up runs.
4. **Deployment stage**
   - Create separate job gated on tags or protected branch to pull image to server and run `docker compose up -d` (or use SSH action to update running container).
   - Include health check curl to ensure service is up post-deploy.
5. **Observability & notifications**
   - Emit workflow artifacts (coverage, test results).
   - Optional Slack/webhook notification on failure/success.

## References
- Git stage reference: `stage-3-cicd`
- PR checklist anchor: `Stage 3 – CI/CD Automation`
