# build/

The offline pipeline: source data -> derived fields -> `web/`.

Use **relative paths** (`../web`, `../docs`) so the project directory can move.
It will.

`build_site.py` must:

1. run `Research/modeling/audit_all.py` and REFUSE TO PUBLISH on a regression;
2. **stamp the data version BEFORE copying the app file** — a static host can
   serve stale JSON after a successful push, and the failure is silent;
3. copy `web/` -> `docs/`.

Document the targeted rebuilds (one keyframe, one layer, metadata only). A
40-minute full rebuild for a card typo will not be run, so the typo will not
be fixed.
