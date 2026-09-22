"""The agent graph, offline: stub language models, stub stores, and a temporary checkpoint database.

Covers routing in code, the opt-out line appended in code, the revision loop and its limit, and
human approval: pause, resume from a fresh graph, and dispatch holding back a rule-breaking edit.
"""

import json

import pandas as pd
import pytest
from langchain_core.documents import Document
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from retention import agent as A, policy as P

GOOD = f"Hi there! You can get {P.OFFER_TERMS['discount']}. Reply YES to add it."
BAD = 'Hi there! You can get money off.'


class Structured:
    def __init__(self, schema, respond):
        self.schema, self.respond = schema, respond

    def invoke(self, messages):
        return self.respond(self.schema, messages)


class StubModel:
    """Stands in for a chat model: `respond(schema, messages)` returns an instance of `schema`."""

    def __init__(self, respond):
        self.respond, self.calls = respond, 0

    def with_structured_output(self, schema):
        def counted(schema, messages):
            self.calls += 1
            return self.respond(schema, messages)
        return Structured(schema, counted)


class Store:
    def __init__(self, docs):
        self.docs = docs

    def similarity_search(self, query, k = 4, filter = None):
        docs = [d for d in self.docs if not filter or all(d.metadata.get(key) == v for key, v in filter.items())]
        return docs[:k]


def drafter(messages_by_attempt):
    """Returns the scripted body for each attempt, repeating the last one."""
    attempts = {}
    def respond(schema, messages):
        prompt = messages[-1][1]
        account = next(line for line in prompt.splitlines() if line.startswith('Why')).split('account ')[-1]
        attempts[account] = attempts.get(account, 0) + 1
        body = messages_by_attempt[min(attempts[account], len(messages_by_attempt)) - 1]
        return schema(message = body, rationale = 'scripted')
    return respond


def judge(schema, messages):
    return schema(terms_accurate = 5, friendly_and_direct = 5, no_pressure = 5, respects_privacy = 5, issues = [])


def customers(ids):
    return [{'account_id': i, 'offer': 'discount', 'offer_name': 'discount', 'offer_terms': P.OFFER_TERMS['discount'],
             'why': f'test account {i}'} for i in ids]


@pytest.fixture
def world():
    snapshot = pd.DataFrame({
        'account_id': [1, 2, 3], 'unresolved_ticket': [False, True, False], 'do_not_contact': False,
        'last_offer_month': pd.array([pd.NA] * 3, dtype = 'Int64'), 'last_offer': None,
        'last_offer_accepted': pd.array([pd.NA] * 3, dtype = 'boolean'), 'late_payments_3m': 0, 'tenure': 24,
        'device_age': 30, 'months_to_payoff': 0, 'plan': 'unlimited'})
    notes = Store([Document(page_content = 'Cust asked about bill.', metadata = {'account_id': 1, 'month': 22})])
    policy_store = Store([Document(page_content = '## Message standards\n- plain')])
    return snapshot, notes, policy_store


def run_until_approval(world, ids, bodies, tmp_path):
    drafter_model = StubModel(drafter(bodies))
    snapshot, notes, policy_store = world
    tools = A.make_tools(customers(ids), {}, notes, policy_store, snapshot, 24)
    with SqliteSaver.from_conn_string(str(tmp_path / 'checkpoints.sqlite')) as saver:
        graph = A.build_graph(drafter_model, StubModel(judge), tools, saver, tmp_path / 'outbox.jsonl')
        config = {'configurable': {'thread_id': 't'}}
        graph.invoke({'month': 24, 'budget': 1000.0}, config)
        state = graph.get_state(config)
    return state, drafter_model, tools


def by_account(state):
    return {d['account_id']: d for d in state.values['drafts']}


def test_routing_happens_in_code_without_a_draft(world, tmp_path):
    state, drafter_model, _ = run_until_approval(world, [2], [GOOD], tmp_path)
    draft = by_account(state)[2]
    assert draft['action'] == 'care_follow_up' and draft['message'] == ''
    assert drafter_model.calls == 0


def test_opt_out_is_appended_and_first_draft_passes(world, tmp_path):
    state, _, _ = run_until_approval(world, [1], [GOOD], tmp_path)
    draft = by_account(state)[1]
    assert draft['message'].endswith(P.OPT_OUT) and draft['passed'] and draft['attempts'] == 1
    assert state.next == ('human_approval',)


def test_failed_draft_is_revised(world, tmp_path):
    state, _, _ = run_until_approval(world, [1], [BAD, GOOD], tmp_path)
    draft = by_account(state)[1]
    assert draft['passed'] and draft['attempts'] == 2


def test_revisions_stop_after_two(world, tmp_path):
    state, _, _ = run_until_approval(world, [1], [BAD], tmp_path)
    draft = by_account(state)[1]
    assert not draft['passed'] and draft['attempts'] == A.MAX_REVISIONS + 1


def test_resume_from_a_fresh_graph_and_block_a_bad_edit(world, tmp_path):
    state, _, tools = run_until_approval(world, [1, 3], [GOOD], tmp_path)
    decisions = {'approve': [1], 'edits': {'3': 'Hi there! $10 off for 6 months.'}}
    with SqliteSaver.from_conn_string(str(tmp_path / 'checkpoints.sqlite')) as saver:
        fresh = A.build_graph(StubModel(drafter([GOOD])), StubModel(judge), tools, saver, tmp_path / 'outbox.jsonl')
        final = fresh.invoke(Command(resume = decisions), {'configurable': {'thread_id': 't'}})
    sent = [json.loads(line) for line in (tmp_path / 'outbox.jsonl').read_text().splitlines() if line]
    assert [m['account_id'] for m in sent] == [1]
    assert final['report']['sent'] == 1
