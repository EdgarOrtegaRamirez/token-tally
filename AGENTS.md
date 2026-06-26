# AGENTS.md — Notes for AI Agents

## Project: Token Tally

### What It Does
Token Tally is a CLI tool and Python library for tracking AI token usage and costs across multiple providers (OpenAI, Anthropic, Google, etc.). It stores usage data in SQLite and provides cost analysis, trend detection, and budget alerts.

### Quick Start
```bash
# Install
pip install token-tally

# Record usage
token-tally add --model gpt-4o --provider openai --input-tokens 1000 --output-tokens 500

# View summary
token-tally summary
```

### Key Files
- `token_tally/models.py` - Data models (UsageEntry, CostSummary, ModelInfo, pricing catalog)
- `token_tally/storage.py` - SQLite-backed storage engine
- `token_tally/analyzer.py` - Usage analysis (trends, spikes, budget alerts)
- `token_tally/cli.py` - Click-based CLI with 10 commands
- `token_tally/output.py` - Rich CLI output helpers

### Important Details
- Data stored in `~/.token_tally/tally.db` (SQLite with WAL mode)
- Built-in pricing catalog for 12 popular models
- Costs are computed on-demand using model catalog pricing
- Default pricing for unknown models: $10/M input, $30/M output
- All timestamps are UTC
- Provider enum: openai, anthropic, google, groq, openrouter, local

### Testing
```bash
pytest tests/ -v
```
74 tests covering models, storage, analyzer, and CLI.

### Adding a New Model
Add to `MODEL_CATALOG` in `token_tally/models.py`:
```python
"new-model": ModelInfo(
    name="new-model", provider=Provider.OPENAI,
    input_price_per_million=5.00, output_price_per_million=15.00,
    max_context=128_000, supports_images=True, supports_tools=True,
),
```

### Common Pitfalls
- Pydantic v2: use `model_validator(mode="after")` for computed fields, not `__post_init__`
- Database: always use `storage.get_entries()` with filters to avoid loading all data
- CLI: storage and analyzer are stored in Click context via `ctx.ensure_object(dict)`
- UUIDs: `id` field uses `uuid.uuid4().hex` for guaranteed uniqueness
