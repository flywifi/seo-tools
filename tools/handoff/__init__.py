"""tools/handoff: the async compute hand-off (P60).

A cloud surface CREATES a job ticket (JSON, shared/schemas/compute-job.json) in the Drive hub's
Jobs/queue/. The local machine validates it, runs ONLY an allowlisted job type through the existing
tool CLIs, and CREATES a result in Jobs/results/. Tickets are never edited; completion is the
existence of the result file. Three transports feed the same queue (Drive for desktop sync, Drive
API polling, remote MCP submit) so there is exactly one execution path to audit.

Modules: queue.py (tickets/results, atomic writes, validation), runner.py (allowlist -> subprocess,
timeouts, idempotency), watcher.py (transport frontends). Non-negotiables and the regression map
live in tools/handoff/MAINTAINER_README.md. Everything is gated on the compute_handoff_enabled
capability (default off).
"""
