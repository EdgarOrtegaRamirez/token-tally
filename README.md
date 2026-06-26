# Token Tally — AI Token Usage Tracker & Cost Analyzer

Track and analyze your AI model token usage and costs across OpenAI, Anthropic, Google, and other providers.

## Features

- **Multi-provider support**: OpenAI, Anthropic, Google, Groq, OpenRouter, local models
- **Built-in pricing catalog**: 12 popular models with current pricing
- **SQLite storage**: Fast, local, zero configuration
- **Rich CLI**: 10 commands for tracking, analysis, and reporting
- **Cost analysis**: Model breakdown, provider breakdown, budget alerts
- **Trend detection**: Usage trends, spike detection, cost monitoring
- **JSON export**: Machine-readable output for integrations
- **Custom pricing**: Works with any model, even those not in the catalog

## Quick Start

### Installation

```bash
pip install token-tally
```

### Record Usage

```bash
# Track a GPT-4o request
token-tally add \
  --model gpt-4o \
  --provider openai \
  --input-tokens 1500 \
  --output-tokens 800 \
  --duration 12.5 \
  --project my-app

# Track a Claude request
token-tally add \
  --model claude-3.5-sonnet \
  --provider anthropic \
  --input-tokens 2000 \
  --output-tokens 1200 \
  --duration 18.0 \
  --project my-app
```

### View Summary

```bash
# Overall costs
token-tally summary

# Filter by project
token-tally summary --project my-app
```

### List Entries

```bash
token-tally list --limit 10
token-tally list --model gpt-4o
```

### Export Data

```bash
token-tally export > usage.json
token-tally export --project my-app
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `add` | Record a new usage entry |
| `list` | List recent usage entries |
| `summary` | Show cost summary and overview |
| `models` | List tracked models with usage stats |
| `trends` | Show usage trends and analysis |
| `alerts` | Check for budget alerts |
| `export` | Export usage data as JSON |
| `clear` | Clear usage entries |
| `sample-config` | Print sample configuration |
| `version` | Show version information |

### `add` Command Options

| Option | Required | Description |
|--------|----------|-------------|
| `--model` | Yes | Model name (e.g., `gpt-4o`, `claude-3.5-sonnet`) |
| `--provider` | Yes | Provider (`openai`, `anthropic`, `google`, `groq`, `openrouter`, `local`) |
| `--input-tokens` | Yes | Number of input tokens |
| `--output-tokens` | Yes | Number of output tokens |
| `--project` | No | Project name (default: `default`) |
| `--session` | No | Session identifier (default: `default`) |
| `--duration` | No | Request duration in seconds |
| `--task-type` | No | Task type (`general`, `chat`, `code`, `summarization`, etc.) |
| `--prompt-template` | No | Prompt template name |
| `--metadata` | No | Additional metadata as JSON string |

## Supported Models & Pricing

The built-in catalog includes:

| Model | Provider | Input ($/M) | Output ($/M) |
|-------|----------|-------------|--------------|
| gpt-4o | OpenAI | $2.50 | $10.00 |
| gpt-4o-mini | OpenAI | $0.15 | $0.60 |
| gpt-4-turbo | OpenAI | $10.00 | $30.00 |
| gpt-4 | OpenAI | $30.00 | $60.00 |
| claude-3.5-sonnet | Anthropic | $3.00 | $15.00 |
| claude-3-opus | Anthropic | $15.00 | $75.00 |
| claude-3.5-haiku | Anthropic | $0.80 | $4.00 |
| gemini-1.5-pro | Google | $1.25 | $5.00 |
| gemini-1.5-flash | Google | $0.075 | $0.30 |
| llama-3.1-405b | OpenRouter | $3.00 | $4.00 |
| llama-3.1-70b | OpenRouter | $0.90 | $1.00 |
| mistral-large | OpenRouter | $2.00 | $6.00 |

## Programmatic Usage

```python
from token_tally.models import UsageEntry, Provider
from token_tally.storage import TokenStorage
from token_tally.analyzer import UsageAnalyzer

# Create storage (uses ~/.token_tally/tally.db by default)
storage = TokenStorage()

# Add an entry
entry = UsageEntry(
    model="gpt-4o",
    provider=Provider.OPENAI,
    input_tokens=1500,
    output_tokens=800,
    duration_seconds=12.5,
    project="my-app",
    task_type="chat",
)
storage.add_entry(entry)

# Get cost summary
summary = storage.get_cost_summary()
print(f"Total cost: ${summary.total_cost_usd:.4f}")

# Get analyzer for insights
analyzer = UsageAnalyzer(storage)
overview = analyzer.get_overview()
alerts = analyzer.get_budget_alerts()
```

## Architecture

```
token-tally/
├── pyproject.toml          # Package config
├── token_tally/            # Main package
│   ├── __init__.py         # Package init
│   ├── models.py           # Data models (UsageEntry, CostSummary, pricing)
│   ├── storage.py          # SQLite storage engine
│   ├── analyzer.py         # Usage analysis & insights
│   ├── output.py           # Rich CLI output helpers
│   └── cli.py              # CLI commands
├── tests/                  # Test suite
│   ├── test_models.py      # Model tests
│   ├── test_storage.py     # Storage tests
│   ├── test_analyzer.py    # Analyzer tests
│   └── test_cli.py         # CLI tests
├── .github/workflows/ci.yml # CI pipeline
├── LICENSE
├── SECURITY.md
└── AGENTS.md
```

## Data Storage

All data is stored in a local SQLite database at `~/.token_tally/tally.db`.

The database schema:
- `usage_entries`: Main table for usage records
- `models`: Model pricing catalog
- Indexed on project, timestamp, model, and session for fast queries

## License

MIT License — see [LICENSE](LICENSE) for details.

## Links

- **Repository**: [github.com/EdgarOrtegaRamirez/token-tally](https://github.com/EdgarOrtegaRamirez/token-tally)
- **Issues**: [github.com/EdgarOrtegaRamirez/token-tally/issues](https://github.com/EdgarOrtegaRamirez/token-tally/issues)
