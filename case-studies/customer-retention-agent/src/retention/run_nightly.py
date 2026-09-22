"""The nightly job. Run from the case study folder:

    PYTHONPATH=src python -m retention.run_nightly --month 24                              # plan, draft, pause
    PYTHONPATH=src python -m retention.run_nightly --month 24 --resume decisions.json      # finish after approval

Each night it checks the churn model's inputs for drift and its calibration on the last known
month, retrains if either check fails, plans the night's offers, and runs the agent up to human
approval. Everything it produces goes to `outputs/nightly/month-<N>/`.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import joblib
import pandas as pd

FOLDER = Path(__file__).resolve().parents[2]
MODELS = FOLDER / 'outputs' / 'models'


def load_or_train(rows, month, log):
    """The churn and uplift models, retrained when monitoring says the churn model has gone stale."""

    from . import monitoring as M, pipeline as PL

    MODELS.mkdir(parents = True, exist_ok = True)
    churn_path, uplift_path = MODELS / 'churn.joblib', MODELS / 'uplift.joblib'

    if uplift_path.exists():
        uplift = joblib.load(uplift_path)
    else:
        uplift = PL.train_uplift_models(rows)
        joblib.dump(uplift, uplift_path)

    churn = joblib.load(churn_path) if churn_path.exists() else None
    reasons = []
    if churn is None:
        reasons = ['no model yet']
    else:
        trained = churn.trained_through
        current, last = rows[rows['month'] == month], rows[rows['month'] == month - 1]
        drift = M.drift_report(last, current)
        against_training = M.drift_report(rows[rows['month'].between(trained - PL.TRAINING_WINDOW, trained - 1)], current)
        calibration = M.calibration_gap(churn.probabilities(last)['p_churn_30'], last['left_next_month']) if len(last) else None
        retrain, reasons = M.should_retrain(drift, calibration)
        log['drift_since_last_month'] = drift.round(3).reset_index(names = 'input').to_dict('records')
        log['drift_against_training'] = against_training.round(3).reset_index(names = 'input').to_dict('records')
        log['calibration_last_month'] = calibration
        if not retrain:
            reasons = []

    if reasons:
        churn = PL.train_churn_model(rows, month)
        joblib.dump(churn, churn_path)
    log['retrained'] = reasons
    log['churn_model_trained_through'] = churn.trained_through

    return churn, uplift


def run(month, budget, batch, out):
    from . import pipeline as PL

    started, log = time.time(), {'month': month, 'budget': budget}
    rows = PL.account_months(month)
    churn, (uplift_models, accept_rates, gated) = load_or_train(rows, month, log)
    tonight, scores, plan, summary = PL.plan_night(rows, month, churn, uplift_models, accept_rates, gated, budget, seed = month)
    out.mkdir(parents = True, exist_ok = True)
    plan.to_parquet(out / 'plan.parquet', index = False)
    log |= {'gated_offers': gated, 'plan': summary, 'mean_predicted_churn_90': float(scores['p_churn_90'].mean())}

    if batch:
        log['agent'] = run_agent(month, tonight, plan, batch, out)
    log['seconds'] = round(time.time() - started, 1)
    (out / 'run_log.json').write_text(json.dumps(log, indent = 1, default = str))

    return log


def agent_parts(month, tonight, out):
    sys.modules.setdefault('tensorflow', None)   # see section 03
    os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
    from langchain_core.globals import set_llm_cache
    from langchain_openai import ChatOpenAI
    from . import agent as A, data

    if not os.environ.get('OPENAI_API_KEY'):
        env_file = FOLDER.parents[1] / 'selected-work' / '.env'
        if env_file.exists():
            os.environ['OPENAI_API_KEY'] = next((line.split('=', 1)[1].strip().strip('"\'') for line in env_file.read_text().splitlines()
                                                 if line.strip().startswith('OPENAI_API_KEY')), '')
    set_llm_cache(A.thread_safe_cache(FOLDER / 'cache' / 'llm_cache.sqlite'))
    notes = data.load('care_notes')
    topics = pd.read_parquet(FOLDER / 'outputs' / 'note_topics.parquet')
    note_store, policy_store = A.build_stores(notes, topics, data.load_policy(), A.SentenceEmbeddings())
    llm = ChatOpenAI(model = 'gpt-4o-mini', temperature = 0)

    return A, llm, note_store, policy_store


def run_agent(month, tonight, plan, batch, out):
    """Drafts messages for the night's top `batch` customers and stops at human approval."""

    from langgraph.checkpoint.sqlite import SqliteSaver

    A, llm, note_store, policy_store = agent_parts(month, tonight, out)
    chosen = plan[~plan['holdout']].sort_values('net_value', ascending = False).head(batch)
    customers = [A.customer_brief(r) for r in chosen.itertuples()]
    tools = A.make_tools(customers, {'batch': len(customers)}, note_store, policy_store, tonight, month)
    with SqliteSaver.from_conn_string(str(out / 'checkpoints.sqlite')) as checkpointer:
        graph = A.build_graph(llm, llm, tools, checkpointer, out / 'outbox.jsonl')
        config = {'configurable': {'thread_id': f'night-{month}'}, 'max_concurrency': 8}
        graph.invoke({'month': month, 'budget': float(plan['exposure'].sum())}, config)
        state = graph.get_state(config)
    review = {'waiting_at': list(state.next), 'review': state.values['review'],
              'drafts': [{k: d[k] for k in ('account_id', 'offer', 'action', 'message', 'rationale', 'passed')} for d in state.values['drafts']]}
    (out / 'review.json').write_text(json.dumps(review, indent = 1))

    return state.values['review']


def resume(month, decisions_path, out):
    """Finishes a paused night with a reviewer's decisions: {"approve": [...], "reject": [...], "edits": {...}}."""

    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.types import Command
    from . import pipeline as PL

    tonight = PL.snapshot(PL.account_months(month), month)
    plan = pd.read_parquet(out / 'plan.parquet')
    A, llm, note_store, policy_store = agent_parts(month, tonight, out)
    customers = [A.customer_brief(r) for r in plan.itertuples()]
    tools = A.make_tools(customers, {}, note_store, policy_store, tonight, month)
    decisions = json.loads(Path(decisions_path).read_text())
    with SqliteSaver.from_conn_string(str(out / 'checkpoints.sqlite')) as checkpointer:
        graph = A.build_graph(llm, llm, tools, checkpointer, out / 'outbox.jsonl')
        final = graph.invoke(Command(resume = decisions), {'configurable': {'thread_id': f'night-{month}'}})
    (out / 'report.json').write_text(json.dumps(final['report'], indent = 1, default = str))

    return final['report']


def main(argv = None):
    parser = argparse.ArgumentParser(description = 'Plan tonight\'s retention offers and draft messages for approval.')
    parser.add_argument('--month', type = int, default = 24)
    parser.add_argument('--budget', type = float, default = 40_000)
    parser.add_argument('--batch', type = int, default = 40, help = 'customers the agent drafts for; 0 plans only')
    parser.add_argument('--resume', help = 'a reviewer\'s decisions file, to finish a paused night')
    args = parser.parse_args(argv)

    out = FOLDER / 'outputs' / 'nightly' / f'month-{args.month}'
    result = resume(args.month, args.resume, out) if args.resume else run(args.month, args.budget, args.batch, out)
    print(json.dumps(result, indent = 1, default = str))


if __name__ == '__main__':
    main()
