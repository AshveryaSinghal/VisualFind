"""Operator-run commands (invoked with `python -m app.scripts.<name>`), as
opposed to app/routers/ (HTTP-triggered) or app/services/indexing/runner.py
(background-task-triggered). Each script opens its own DB session and is
safe to run against a live database while the app is running."""
