#!/usr/bin/env python3
"""Recognize approved literal calls only; does not source env or execute helper."""
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True

try:
    scripts = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('native_knowledge_broker', scripts / 'planner_shell.py')
    broker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(broker)
    argv = broker.literal_argv(json.load(sys.stdin)['command'])
    helpers = {'knowledge_search.sh', 'knowledge_status.sh', 'knowledge_status_engram.sh', 'knowledge_status_qdrant.sh', 'knowledge_inventory.sh', 'knowledge_store.sh', 'knowledge_seed_global.sh'}
    direct = len(argv) >= 2 and argv[0] == 'bash' and Path(argv[1]).expanduser() in {scripts / name for name in helpers}
    through_broker = len(argv) >= 4 and argv[0] == 'python3' and Path(argv[1]).expanduser() == scripts / 'planner_shell.py' and argv[2] == 'helper' and argv[3] in ('knowledge-search', 'knowledge-status')
    print(json.dumps(direct or through_broker))
except Exception:
    print('Knowledge call must be literal and recognized; values suppressed', file=sys.stderr)
    raise SystemExit(2)
