# Token Tally - AI Token Usage Tracker & Cost Analyzer
# SPDX-License-Identifier: MIT

"""Core data models for token tracking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Provider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    LOCAL = "local"


class ModelInfo(BaseModel):
    """Information about an AI model's pricing."""

    name: str
    provider: Provider
    input_price_per_million: float = Field(ge=0, description="Price per million input tokens in USD")
    output_price_per_million: float = Field(ge=0, description="Price per million output tokens in USD")
    max_context: int = Field(ge=1, description="Maximum context window size")
    supports_images: bool = False
    supports_tools: bool = False


# Built-in model catalog
MODEL_CATALOG: dict[str, ModelInfo] = {
    "gpt-4o": ModelInfo(
        name="gpt-4o", provider=Provider.OPENAI,
        input_price_per_million=2.50, output_price_per_million=10.00,
        max_context=128_000, supports_images=True, supports_tools=True,
    ),
    "gpt-4o-mini": ModelInfo(
        name="gpt-4o-mini", provider=Provider.OPENAI,
        input_price_per_million=0.15, output_price_per_million=0.60,
        max_context=128_000, supports_images=True, supports_tools=True,
    ),
    "gpt-4-turbo": ModelInfo(
        name="gpt-4-turbo", provider=Provider.OPENAI,
        input_price_per_million=10.00, output_price_per_million=30.00,
        max_context=128_000, supports_images=True, supports_tools=True,
    ),
    "gpt-4": ModelInfo(
        name="gpt-4", provider=Provider.OPENAI,
        input_price_per_million=30.00, output_price_per_million=60.00,
        max_context=8_192, supports_tools=True,
    ),
    "claude-3.5-sonnet": ModelInfo(
        name="claude-3.5-sonnet", provider=Provider.ANTHROPIC,
        input_price_per_million=3.00, output_price_per_million=15.00,
        max_context=200_000, supports_images=True, supports_tools=True,
    ),
    "claude-3-opus": ModelInfo(
        name="claude-3-opus", provider=Provider.ANTHROPIC,
        input_price_per_million=15.00, output_price_per_million=75.00,
        max_context=200_000, supports_images=True, supports_tools=True,
    ),
    "claude-3.5-haiku": ModelInfo(
        name="claude-3.5-haiku", provider=Provider.ANTHROPIC,
        input_price_per_million=0.80, output_price_per_million=4.00,
        max_context=200_000, supports_images=True, supports_tools=True,
    ),
    "gemini-1.5-pro": ModelInfo(
        name="gemini-1.5-pro", provider=Provider.GOOGLE,
        input_price_per_million=1.25, output_price_per_million=5.00,
        max_context=2_000_000, supports_images=True, supports_tools=True,
    ),
    "gemini-1.5-flash": ModelInfo(
        name="gemini-1.5-flash", provider=Provider.GOOGLE,
        input_price_per_million=0.075, output_price_per_million=0.30,
        max_context=2_000_000, supports_images=True, supports_tools=True,
    ),
    "llama-3.1-405b": ModelInfo(
        name="llama-3.1-405b", provider=Provider.OPENROUTER,
        input_price_per_million=3.00, output_price_per_million=4.00,
        max_context=131_072, supports_tools=True,
    ),
    "llama-3.1-70b": ModelInfo(
        name="llama-3.1-70b", provider=Provider.OPENROUTER,
        input_price_per_million=0.90, output_price_per_million=1.00,
        max_context=131_072, supports_tools=True,
    ),
    "mistral-large": ModelInfo(
        name="mistral-large", provider=Provider.OPENROUTER,
        input_price_per_million=2.00, output_price_per_million=6.00,
        max_context=131_072, supports_tools=True,
    ),
}


class UsageEntry(BaseModel):
    """A single tracked usage entry for a token request."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    project: str = Field(default="default")
    session: str = Field(default="default")
    model: str
    provider: Provider = Field(default=Provider.OPENAI)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    prompt_template: str = Field(default="")
    task_type: str = Field(default="general")
    metadata: dict = Field(default_factory=dict)

    # Computed fields (set by model_validator)
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    @model_validator(mode="after")
    def _compute_fields(self):
        """Compute derived fields after validation."""
        self.total_tokens = self.input_tokens + self.output_tokens
        self.estimated_cost_usd = round(self._compute_cost(), 8)
        return self

    def _compute_cost(self) -> float:
        """Compute cost based on model pricing."""
        model_info = MODEL_CATALOG.get(self.model)
        if model_info is None:
            input_price = 10.00 / 1_000_000
            output_price = 30.00 / 1_000_000
        else:
            input_price = model_info.input_price_per_million / 1_000_000
            output_price = model_info.output_price_per_million / 1_000_000
        return (self.input_tokens * input_price) + (self.output_tokens * output_price)

    @property
    def cost_per_thousand(self) -> float:
        """Cost per thousand tokens."""
        total = self.total_tokens
        if total == 0:
            return 0.0
        return self.estimated_cost_usd / (total / 1000)

    @property
    def tokens_per_second(self) -> float:
        """Tokens generated per second (throughput)."""
        if self.duration_seconds <= 0:
            return 0.0
        return self.output_tokens / self.duration_seconds


class CostSummary(BaseModel):
    """Summary of costs for a given period or project."""

    project: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    entry_count: int = 0
    average_cost_per_request: float = 0.0
    average_tokens_per_request: float = 0.0
    model_breakdown: dict[str, dict[str, float]] = Field(default_factory=dict)
    provider_breakdown: dict[str, dict[str, float]] = Field(default_factory=dict)

    @property
    def formatted_total_cost(self) -> str:
        """Formatted cost string."""
        if self.total_cost_usd < 0.01:
            return f"${self.total_cost_usd * 100:.2f}\u00a2"
        return f"${self.total_cost_usd:.2f}"

    @property
    def formatted_average_cost(self) -> str:
        """Formatted average cost string."""
        if self.entry_count == 0:
            return "$0.00"
        if self.average_cost_per_request < 0.01:
            return f"${self.average_cost_per_request * 100:.2f}\u00a2"
        return f"${self.average_cost_per_request:.2f}"
