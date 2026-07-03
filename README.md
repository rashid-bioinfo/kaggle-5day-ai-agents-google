# Kaggle 5-Day AI Agents Intensive: Vibe Coding With Google

This repository is my working notebook and code workspace for the
[5-Day AI Agents: Intensive Vibe Coding Course With Google](https://www.kaggle.com/competitions/5-day-ai-agents-intensive-vibecoding-course-with-google/discussion/708744)
on Kaggle.

The course is focused on building agentic applications with modern AI tooling:
vibe coding, Google agent tooling, agent interoperability, skills, evaluation,
and practical app scaffolding. This repo captures the slides, experiments,
generated projects, and implementation notes I created while working through
the course.

## Repository Goals

- Keep course artifacts, code, and experiments in one auditable workspace.
- Practice AI-assisted software development with meaningful commits.
- Explore agent scaffolding using Google Agents CLI, ADK-style app structure,
  Gemini models, and agent utilities.
- Build small but runnable examples instead of only reading course material.
- Preserve enough setup detail that the exercises can be revisited later.

## Course Progress

| Day | Topic | Local artifacts | Status |
| --- | --- | --- | --- |
| Day 1 | The new SDLC with vibe coding | `1_Day1/` | Added slides and starter project |
| Day 2 | Agent tools and interoperability | `2_Day2/` | Added course slides |
| Day 3 | Agent skills | `3_Day3/` | Added slides and skill examples |
| Day 4 | In progress / to be added | TBD | Pending |
| Day 5 | In progress / to be added | TBD | Pending |

## Repository Layout

```text
.
├── 1_Day1/
│   ├── The New SDLC With Vibe Coding_Day_1.pdf
│   └── my-first-project/
├── 2_Day2/
│   └── Agent Tools & Interoperability_Day_2.pdf
├── 3_Day3/
│   ├── Agent Skills_Day_3.pdf
│   └── antigravity-skills/
├── agy-cli-projects/
│   ├── bq-releases-notes/
│   ├── customer-support-agent/
│   └── myProject/
│       └── weather-assistant/
├── .gitignore
└── README.md
```

## Main Projects

### BigQuery Release Notes Tracker

Path: `agy-cli-projects/bq-releases-notes/`

A Flask web application that fetches and parses the Google Cloud BigQuery
release notes Atom feed, splits release-note entries into cards, supports
client-side filtering/search, and includes a tweet/X composer workflow.

Key files:

- `app.py` - Flask backend, Atom feed retrieval, parsing, and caching.
- `templates/index.html` - Main HTML interface.
- `static/css/style.css` - Dashboard styling.
- `static/js/app.js` - Client-side state, filtering, and composer behavior.

Run:

```bash
cd agy-cli-projects/bq-releases-notes
python3 -m venv .venv
source .venv/bin/activate
pip install flask requests beautifulsoup4
python app.py
```

Then open `http://localhost:5000`.

### Customer Support Agent

Path: `agy-cli-projects/customer-support-agent/`

An Agents CLI scaffolded project adapted into a customer-support agent workflow.
The current agent classifies user requests as shipping-related or unrelated,
routes shipping questions to a shipping FAQ agent, and declines unrelated
queries with a bounded support response.

Key files:

- `app/agent.py` - Main workflow and routing logic.
- `app/fast_api_app.py` - FastAPI wrapper.
- `app/app_utils/` - A2A, service, telemetry, and typing utilities.
- `tests/` - Unit, integration, and evaluation scaffolding.
- `pyproject.toml` and `uv.lock` - Python package/dependency definition.

Typical development flow:

```bash
cd agy-cli-projects/customer-support-agent
agents-cli install
agents-cli playground
```

### Weather Assistant

Path: `agy-cli-projects/myProject/weather-assistant/`

An Agents CLI scaffolded project for experimenting with a simple assistant
structure, app utilities, FastAPI serving, evaluation datasets, and generated
agent project conventions.

Typical development flow:

```bash
cd agy-cli-projects/myProject/weather-assistant
agents-cli install
agents-cli playground
```

### Antigravity / Gemini CLI Skills

Path: `3_Day3/antigravity-skills/`

Examples for building reusable agent skills. This folder includes progressive
examples ranging from pure prompt routing to deterministic validation scripts.

Included skill examples:

- `git-commit-formatter`
- `license-header-adder`
- `json-to-pydantic`
- `database-schema-validator`
- `always-verify-gcp`

## Setup Notes

The projects in this repository use a mix of Python, Flask, Google agent
tooling, and generated scaffold files. The exact requirements vary by subproject.

Common tools:

- Python 3.10+
- `uv`
- `google-agents-cli`
- Google Cloud SDK, if deploying or using cloud services
- GitHub CLI, for repository publishing

Install Agents CLI tooling:

```bash
uvx google-agents-cli setup
```

Install dependencies inside an agent project:

```bash
agents-cli install
```

Run an agent playground:

```bash
agents-cli playground
```

Run tests in agent projects:

```bash
uv run pytest tests/unit tests/integration
```

## Environment And Secrets

Local runtime files and secrets are intentionally ignored:

- `.env`
- `.env.*`
- `.venv/`
- `__pycache__/`
- `.adk/`
- `.google-agents-cli/`
- `*.log`

Use `.env.example` files as templates. Do not commit real API keys, service
account credentials, OAuth tokens, or private patient/research data.

## Learning Log

### Day 1: Vibe Coding And AI-Native Development

Focus:

- Understanding how AI-assisted coding changes the software development cycle.
- Practicing high-level intent specification with iterative refinement.
- Capturing starter project artifacts and custom local skills.

Artifacts:

- `1_Day1/The New SDLC With Vibe Coding_Day_1.pdf`
- `1_Day1/my-first-project/`

### Day 2: Agent Tools And Interoperability

Focus:

- Understanding tool use in agents.
- Thinking about interoperability and protocol-level design.
- Preparing for agent-to-agent and tool-augmented workflows.

Artifacts:

- `2_Day2/Agent Tools & Interoperability_Day_2.pdf`

### Day 3: Agent Skills

Focus:

- Creating reusable skills for agent behavior.
- Separating instructions, examples, scripts, and static resources.
- Using deterministic validation where prompts alone are not enough.

Artifacts:

- `3_Day3/Agent Skills_Day_3.pdf`
- `3_Day3/antigravity-skills/`

## Reproducibility Practices

This is a learning repository, but it still follows a few research-friendly
software practices:

- Keep generated runtime files out of Git.
- Commit coherent units of work with descriptive messages.
- Prefer examples that can be rerun locally.
- Keep dependency lockfiles where generated for agent projects.
- Use README files to preserve context, assumptions, and run commands.
- Treat AI-generated code as a draft that needs inspection, tests, and review.

## Current Git History

The repository was organized into meaningful commits:

- `Initial course workspace`
- `Add agent app examples`
- `Update customer support agent workflow`
- `Align customer support app entrypoint`
- `Add comprehensive course README`

## Next Steps

- Add Day 4 and Day 5 materials as the course progresses.
- Add screenshots or short demos for each runnable project.
- Add a root `Makefile` with validation commands for subprojects.
- Add a short reflection after each day covering what worked, what failed, and
  what needs deeper review.
- Expand the customer-support agent with test cases for routing and refusals.

## Reference

- Kaggle course discussion:
  [5-Day AI Agents: Intensive Vibe Coding Course With Google](https://www.kaggle.com/competitions/5-day-ai-agents-intensive-vibecoding-course-with-google/discussion/708744)
