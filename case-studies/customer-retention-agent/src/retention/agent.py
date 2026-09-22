"""The retention agent: a LangGraph workflow that turns tonight's plan into approved messages.

The graph never decides who gets an offer, how they're routed, or any number: the optimizer
(section 04) and the policy's hard rules in code do that. The language model reads each customer's
notes and the policy, drafts the message, and reviews drafts against the policy. A person approves
before anything is sent.

    load_plan ─► customer (one branch per customer, in parallel) ─► aggregate ─► human_approval ─► dispatch ─► report
                     │
                     └─ gather_context ─┬─► draft ─► check ─┬─► finalize
                                        │     ▲             │
                                        │     └── revise ◄──┘ (at most twice)
                                        └─► finalize (routed to care follow-up in code: no draft)
"""

import json
import operator
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt
from pydantic import BaseModel, Field

from . import policy

MAX_REVISIONS = 2


def thread_safe_cache(database_path):
    """LangChain's SQLite LLM cache, safe for the graph's parallel branches.

    Two branches can send an identical prompt at once (the judge reviewing two identical messages);
    the stock cache then tries to store the same response twice and fails on its unique key.
    """
    import threading
    from langchain_community.cache import SQLiteCache
    from sqlalchemy.exc import IntegrityError

    class ThreadSafeSQLiteCache(SQLiteCache):
        _lock = threading.Lock()

        def lookup(self, prompt, llm_string):
            with self._lock:
                return super().lookup(prompt, llm_string)

        def update(self, prompt, llm_string, return_val):
            with self._lock:
                try:
                    super().update(prompt, llm_string, return_val)
                except IntegrityError:
                    pass

    return ThreadSafeSQLiteCache(database_path = str(database_path))


# ---------------------------------------------------------------- retrieval

class SentenceEmbeddings(Embeddings):
    """LangChain wrapper for the local sentence model used in section 03."""

    def __init__(self, model_name = 'all-MiniLM-L6-v2'):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts):
        return self.model.encode(list(texts), batch_size = 64, normalize_embeddings = True, show_progress_bar = False).tolist()

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def build_stores(notes, note_topics, policy_text, embeddings):
    """Chroma vector stores for the care notes (with account and month) and the policy's sections."""

    topics = note_topics.set_index('note_id')
    note_docs = [Document(page_content = row.text, metadata = {
        'account_id': int(row.account_id), 'month': int(row.month), 'category': topics.at[row.note_id, 'category']})
        for row in notes.itertuples()]
    sections = [s.strip() for s in policy_text.split('\n## ')[1:]]
    policy_docs = [Document(page_content = '## ' + s, metadata = {'section': s.splitlines()[0]}) for s in sections]

    note_store = Chroma.from_documents(note_docs, embeddings, collection_name = 'care_notes')
    policy_store = Chroma.from_documents(policy_docs, embeddings, collection_name = 'offer_policy')

    return note_store, policy_store


# ---------------------------------------------------------------- structured outputs

class Draft(BaseModel):
    """The agent's proposed outreach for one customer."""

    message: str = Field(description = 'The SMS body, at most 296 characters, without the opt-out line (it is added automatically)')
    rationale: str = Field(description = 'One or two sentences for the reviewer: why this offer and message fit, '
                                         'citing the plan\'s numbers and what the notes say')


class Judgment(BaseModel):
    """A policy review of one draft, each score from 1 (fails) to 5 (fully meets)."""

    terms_accurate: int = Field(ge = 1, le = 5, description = 'The offer and its terms are stated exactly, with nothing added')
    friendly_and_direct: int = Field(ge = 1, le = 5, description = 'Plain, warm, and to the point')
    no_pressure: int = Field(ge = 1, le = 5, description = 'No deadlines, urgency, or guilt')
    respects_privacy: int = Field(ge = 1, le = 5, description = 'Mentions nothing the customer did not share with the carrier, and no churn or risk')
    issues: list[str] = Field(description = 'Specific problems to fix, empty if none')


# ---------------------------------------------------------------- state

class RunState(TypedDict, total = False):
    month: int
    budget: float
    plan: list[dict]
    summary: dict
    drafts: Annotated[list[dict], operator.add]
    review: dict
    decisions: dict
    outbox: list[dict]
    report: dict


class CustomerState(TypedDict, total = False):
    customer: dict
    route: str
    notes: list[str]
    policy: list[str]
    draft: dict
    rule_problems: list[str]
    judgment: dict
    attempts: int
    history: Annotated[list[dict], operator.add]
    drafts: Annotated[list[dict], operator.add]


class CustomerOutput(TypedDict):
    drafts: Annotated[list[dict], operator.add]


# ---------------------------------------------------------------- graph

DRAFT_SYSTEM = """You write retention outreach for a US wireless carrier's customers.
Use only the facts given: the offer and its exact terms, and what the customer's own care notes say.
Follow the policy excerpts exactly. Never mention churn, risk, predictions, or that the customer might leave.
No deadlines or pressure. Never name a competitor. The customer's name is not available: open with "Hi there".
If the notes show what the customer raised, you may acknowledge it briefly in their own terms ("you asked about your bill"),
but never infer or mention anything they didn't say, and never mention the plan's numbers.
Whether to contact the customer, and with which offer, has already been decided: write the message for that offer.
Write only the SMS body, at most 296 characters. Don't add an opt-out line: the required "Reply STOP to opt out." is added
automatically after your text."""

JUDGE_SYSTEM = """You review retention messages against a carrier's offer policy.
Score each criterion from 1 (fails) to 5 (fully meets). Be strict about exact offer terms and about
anything that could feel like pressure or reveal what the carrier inferred about the customer.
Allowed, and not a problem: thanking the customer or appreciating their loyalty; briefly acknowledging,
in the customer's own terms, something the care notes show they told the carrier (for example, that they
asked about their bill). Not allowed: inferring feelings or intentions they didn't express, or referring
to anything that isn't in the notes."""


def with_opt_out(body):
    """The policy's fixed opt-out line, appended in code rather than left to the model."""

    body = body.strip()
    if body.endswith(policy.OPT_OUT):
        body = body[: -len(policy.OPT_OUT)].rstrip()
    return f'{body} {policy.OPT_OUT}'


def build_graph(drafter, judge, tools, checkpointer, outbox_path):
    """The full workflow. `drafter` and `judge` are chat models; `tools` maps names to LangChain tools."""

    drafter = drafter.with_structured_output(Draft)
    judge = judge.with_structured_output(Judgment)

    # Customer subgraph -------------------------------------------------------

    def gather_context(state: CustomerState):
        c = state['customer']
        notes = tools['retrieve_notes'].invoke({'account_id': c['account_id']})
        excerpts = tools['retrieve_policy'].invoke({'offer': c['offer']})
        route = tools['route_customer'].invoke({'account_id': c['account_id']})
        return {'notes': notes, 'policy': excerpts, 'route': route, 'attempts': 0}

    def after_context(state: CustomerState):
        return 'draft' if state['route'] == 'send_offer' else 'finalize'

    def draft(state: CustomerState):
        c = state['customer']
        feedback = ''
        if state.get('draft'):
            problems = state.get('rule_problems', []) + state.get('judgment', {}).get('issues', [])
            feedback = (f"\n\nYour previous draft was:\n{state['draft']['message'].removesuffix(policy.OPT_OUT).rstrip()}\n"
                        f"It was returned for these problems; fix all of them:\n- " + '\n- '.join(problems))
        prompt = (f"Offer: {c['offer_name']}, exactly: {c['offer_terms']}.\n"
                  f"Why this customer was chosen (from the plan's models): {c['why']}\n"
                  f"The customer's care notes, most recent first:\n" + ('\n'.join(f'- {n}' for n in state['notes']) or '- none on file') +
                  f"\n\nPolicy excerpts:\n" + '\n\n'.join(state['policy']) + feedback)
        result = drafter.invoke([('system', DRAFT_SYSTEM), ('user', prompt)]).model_dump()
        result['message'] = with_opt_out(result['message'])
        return {'draft': result, 'attempts': state.get('attempts', 0) + 1}

    def check(state: CustomerState):
        d, c = state['draft'], state['customer']
        problems = tools['check_rules'].invoke({'message': d['message'], 'offer': c['offer'], 'account_id': c['account_id']})
        verdict = judge.invoke([('system', JUDGE_SYSTEM), ('user',
                                 f"Offer, exactly: {c['offer_terms']}.\nPolicy excerpts:\n" + '\n\n'.join(state['policy']) +
                                 f"\n\nWhat the customer told us (care notes):\n" + ('\n'.join(f'- {n}' for n in state['notes']) or '- nothing') +
                                 f"\n\nMessage to review:\n{d['message']}")])
        return {'rule_problems': problems, 'judgment': verdict.model_dump(),
                'history': [{'attempt': state['attempts'], 'message': d['message'], 'rule_problems': problems, 'judgment': verdict.model_dump()}]}

    def passed(state: CustomerState):
        if state['route'] != 'send_offer':
            return True
        scores = [v for k, v in state['judgment'].items() if k != 'issues']
        return not state['rule_problems'] and min(scores) >= 4

    def route(state: CustomerState):
        return 'finalize' if passed(state) or state['attempts'] > MAX_REVISIONS else 'draft'

    def finalize(state: CustomerState):
        c, d = state['customer'], state.get('draft', {})
        return {'drafts': [{
            'account_id': c['account_id'], 'offer': c['offer'], 'action': state['route'], 'message': d.get('message', ''),
            'rationale': d.get('rationale', 'Routed in code: the account has an unresolved support ticket.'),
            'attempts': state['attempts'], 'passed': passed(state),
            'rule_problems': state.get('rule_problems', []), 'judgment': state.get('judgment', {}),
            'notes_used': len(state['notes']), 'history': state.get('history', []),
        }]}

    customer = StateGraph(CustomerState, output_schema = CustomerOutput)
    customer.add_node('gather_context', gather_context)
    customer.add_node('draft', draft)
    customer.add_node('check', check)
    customer.add_node('finalize', finalize)
    customer.add_edge(START, 'gather_context')
    customer.add_conditional_edges('gather_context', after_context, ['draft', 'finalize'])
    customer.add_edge('draft', 'check')
    customer.add_conditional_edges('check', route, ['draft', 'finalize'])
    customer.add_edge('finalize', END)
    customer_graph = customer.compile()

    # Run graph ---------------------------------------------------------------

    def load_plan(state: RunState):
        plan, summary = tools['plan_tonight'].invoke({'budget': state['budget']})
        return {'plan': plan, 'summary': summary}

    def fan_out(state: RunState):
        return [Send('customer', {'customer': c}) for c in state['plan']]

    def aggregate(state: RunState):
        drafts = state['drafts']
        offers = [d for d in drafts if d['action'] == 'send_offer']
        review = {
            'drafts': len(drafts), 'offers_drafted': len(offers),
            'passed': sum(d['passed'] for d in offers), 'passed_first_try': sum(d['passed'] and d['attempts'] == 1 for d in offers),
            'care_follow_up': sum(d['action'] == 'care_follow_up' for d in drafts),
        }
        return {'review': review}

    def human_approval(state: RunState):
        decisions = interrupt({'review': state['review'],
                               'drafts': [{k: d[k] for k in ('account_id', 'offer', 'action', 'message', 'rationale', 'passed')}
                                          for d in state['drafts']]})
        return {'decisions': decisions}

    def dispatch(state: RunState):
        decisions = state['decisions']
        edits = {int(k): v for k, v in decisions.get('edits', {}).items()}
        approved = set(decisions.get('approve', [])) | set(edits)
        outbox = []
        for d in state['drafts']:
            if d['account_id'] in approved and d['action'] == 'send_offer':
                message = edits.get(d['account_id'], d['message'])
                if tools['check_rules'].invoke({'message': message, 'offer': d['offer'], 'account_id': d['account_id']}):
                    continue   # an edit that breaks a hard rule is never sent
                outbox.append({'account_id': d['account_id'], 'offer': d['offer'], 'channel': 'sms', 'message': message,
                               'edited': d['account_id'] in edits})
        Path(outbox_path).write_text('\n'.join(json.dumps(m) for m in outbox) + '\n')
        return {'outbox': outbox}

    def report(state: RunState):
        offers = {d['account_id'] for d in state['drafts'] if d['action'] == 'send_offer'}
        approved = (set(state['decisions'].get('approve', [])) | {int(k) for k in state['decisions'].get('edits', {})}) & offers
        return {'report': {**state['review'], 'approved': len(approved),
                           'sent': len(state['outbox']), 'edited': sum(m['edited'] for m in state['outbox']),
                           'rejected': len(state['decisions'].get('reject', [])), 'plan': state['summary']}}

    run = StateGraph(RunState)
    run.add_node('load_plan', load_plan)
    run.add_node('customer', customer_graph)
    run.add_node('aggregate', aggregate)
    run.add_node('human_approval', human_approval)
    run.add_node('dispatch', dispatch)
    run.add_node('report', report)
    run.add_edge(START, 'load_plan')
    run.add_conditional_edges('load_plan', fan_out, ['customer'])
    run.add_edge('customer', 'aggregate')
    run.add_edge('aggregate', 'human_approval')
    run.add_edge('human_approval', 'dispatch')
    run.add_edge('dispatch', 'report')
    run.add_edge('report', END)

    return run.compile(checkpointer = checkpointer)


# ---------------------------------------------------------------- tools

OFFER_NAMES = {'discount': 'discount', 'device': 'device credit', 'data': 'data upgrade'}


def customer_brief(row):
    """What the drafter is told about one planned customer: the offer, its exact terms, and why they were chosen."""

    reason = row.reason if isinstance(row.reason, str) else 'no clear reason'
    return {'account_id': int(row.account_id), 'offer': row.offer, 'offer_name': OFFER_NAMES[row.offer],
            'offer_terms': policy.OFFER_TERMS[row.offer],
            'why': (f'estimated 90-day churn risk {row.p_churn_90:.1%}; this offer is estimated to lower it by {row.uplift * 100:.1f} points; '
                    f'rep codes point to {reason}; 24-month value about ${row.value:,.0f}')}


def make_tools(plan_customers, plan_summary, note_store, policy_store, snapshot, month):
    """LangChain tools the graph calls. Every number and rule comes from here, not from the model."""

    @tool
    def plan_tonight(budget: float) -> tuple:
        """Tonight's customers, offers, and the numbers behind each, from the optimizer (section 04)."""
        return plan_customers, plan_summary

    @tool
    def retrieve_notes(account_id: int) -> list:
        """The customer's care notes, most relevant to why they might be unhappy first."""
        docs = note_store.similarity_search('what the customer is unhappy about or asked for', k = 4,
                                            filter = {'account_id': int(account_id)})
        return [f"(month {d.metadata['month']}) {d.page_content}" for d in sorted(docs, key = lambda d: -d.metadata['month'])]

    @tool
    def retrieve_policy(offer: str) -> list:
        """The policy sections most relevant to making this offer by SMS."""
        docs = policy_store.similarity_search(f'{offer} offer terms, message standards, contact rules, escalation', k = 4)
        return [d.page_content for d in docs]

    @tool
    def route_customer(account_id: int) -> str:
        """The policy's escalation rule: an unresolved support ticket goes to care follow-up, not an offer."""
        rows = snapshot[snapshot['account_id'] == int(account_id)]
        return 'care_follow_up' if bool(rows['unresolved_ticket'].iloc[0]) else 'send_offer'

    @tool
    def check_rules(message: str, offer: str, account_id: int) -> list:
        """Every hard rule: message rules, exact offer terms, banned content, and eligibility tonight."""
        problems = policy.check_draft(message, offer)
        rows = snapshot[snapshot['account_id'] == int(account_id)]
        if rows.empty or not bool(policy.eligible(rows, month)[offer].iloc[0]):
            problems.append('customer is not eligible for this offer tonight')
        return problems

    return {t.name: t for t in [plan_tonight, retrieve_notes, retrieve_policy, route_customer, check_rules]}
