# Stage 3 – CI/CD Pipeline

## Goal
Automate the homelab workflow so every change is linted/tested and a ready-to-run bundle (Docker image + compose files) is produced without involving a public registry.

## Plan
1. **Runner & triggers**
   - GitHub Actions workflow triggered on `push` and `pull_request`.
   - Nightly `workflow_dispatch` option for manual “rebuild homelab” runs.
2. **Jobs**
   - `lint-and-test`: Python 3.11, install `requirements.txt`, run formatter/lint (ruff or flake8) and `pytest`.
   - `build-and-package`: build Docker image locally (no registry push) and export with `docker save` + tar the `docker-compose.yml` and `.env.example` for easy homelab import.
3. **Caches & secrets**
   - Enable pip cache to keep runs fast.
   - Only secret needed is optional `SSH_PRIVATE_KEY` if we later add remote copy; otherwise workflows run with repo contents alone.
4. **Deployment helper**
   - Provide a job or reusable step that uploads the tarball as a workflow artifact and prints `scripts/start_stack.sh` instructions.
   - Optional manual step (not automated) describing how to `scp` the artifact to the homelab box and run `docker load` + `docker compose up -d`.
5. **Verification & notifications**
   - Publish test results/coverage as artifacts.
   - Simple email/GitHub notification on failures (no Slack/webhooks needed for the toy setup).

## References
- Git stage reference: `stage-3-cicd`
- PR checklist anchor: `Stage 3 – CI/CD Automation`
