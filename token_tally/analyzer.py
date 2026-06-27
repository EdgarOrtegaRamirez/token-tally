# Token Tally - AI Token Usage Tracker & Cost Analyzer
# SPDX-License-Identifier: MIT

"""Usage analyzer engine for token cost insights."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import MODEL_CATALOG
from .storage import TokenStorage


class UsageAnalyzer:
    """Analyze token usage patterns and provide insights."""

    def __init__(self, storage: TokenStorage):
        self.storage = storage

    def get_overview(self) -> dict:
        """Get a high-level overview of all usage."""
        summary = self.storage.get_cost_summary()
        projects = self.storage.get_all_projects()
        models = self.storage.get_all_models()

        now = datetime.now(timezone.utc)
        summary_7d = self.storage.get_cost_summary(
            start_date=now - timedelta(days=7)
        )
        summary_30d = self.storage.get_cost_summary(
            start_date=now - timedelta(days=30)
        )

        return {
            "total_cost": summary.total_cost_usd,
            "total_tokens": summary.total_tokens,
            "total_input": summary.total_input_tokens,
            "total_output": summary.total_output_tokens,
            "total_requests": summary.entry_count,
            "average_cost": summary.average_cost_per_request,
            "average_tokens": summary.average_tokens_per_request,
            "projects": projects,
            "models": models,
            "last_7_days_cost": summary_7d.total_cost_usd,
            "last_7_days_tokens": summary_7d.total_tokens,
            "last_7_days_requests": summary_7d.entry_count,
            "last_30_days_cost": summary_30d.total_cost_usd,
            "last_30_days_tokens": summary_30d.total_tokens,
            "last_30_days_requests": summary_30d.entry_count,
        }

    def get_cost_breakdown(self, project: Optional[str] = None) -> list[dict]:
        """Get cost breakdown by model."""
        breakdown = []
        for model, data in self.storage.get_cost_summary(project=project).model_breakdown.items():
            total_cost = data.get("cost", 0.0)
            total_tokens = data.get("tokens", 0)
            avg_cost_per_k = total_cost / (total_tokens / 1000) if total_tokens > 0 else 0.0
            breakdown.append({
                "model": model, "tokens": total_tokens,
                "cost": round(total_cost, 8),
                "avg_cost_per_k_tokens": round(avg_cost_per_k, 8),
            })
        breakdown.sort(key=lambda x: x["cost"], reverse=True)
        return breakdown

    def get_trend_analysis(self, days: int = 30) -> list[dict] | dict:
        """Analyze trends in usage over time."""
        daily_stats = self.storage.get_daily_stats(days)
        if len(daily_stats) < 2:
            return daily_stats

        mid = len(daily_stats) // 2
        first_half = daily_stats[:mid]
        second_half = daily_stats[mid:]

        if first_half and second_half:
            first_avg = sum(d["cost"] for d in first_half) / len(first_half)
            second_avg = sum(d["cost"] for d in second_half) / len(second_half)
            change_pct = ((second_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0.0
        else:
            change_pct = 0.0

        return {
            "daily_stats": daily_stats,
            "trend_direction": "increasing" if change_pct > 10 else ("decreasing" if change_pct < -10 else "stable"),
            "cost_change_pct": round(change_pct, 1),
        }

    def detect_spikes(self, project: Optional[str] = None, threshold_multiplier: float = 2.0) -> list[dict]:
        """Detect usage spikes (days with unusually high token usage)."""
        summary = self.storage.get_cost_summary(project=project)
        daily_stats = self.storage.get_daily_stats(days=90)
        if len(daily_stats) < 3:
            return []

        avg_daily = summary.total_tokens / len(daily_stats) if daily_stats else 0
        spikes = []
        for day in daily_stats:
            if day["tokens"] > avg_daily * threshold_multiplier and avg_daily > 0:
                spikes.append({
                    "day": day["day"], "tokens": day["tokens"],
                    "avg": int(avg_daily),
                    "multiplier": round(day["tokens"] / avg_daily, 1),
                    "cost": day["cost"],
                })
        return spikes

    def get_model_efficiency(self, project: Optional[str] = None) -> list[dict]:
        """Analyze cost efficiency by model."""
        entries = self.storage.get_entries(project=project, limit=10000)
        model_stats: dict[str, dict] = {}

        for entry in entries:
            model = entry.model
            if model not in model_stats:
                model_stats[model] = {
                    "model": model, "total_requests": 0,
                    "total_tokens": 0, "total_cost": 0.0,
                    "duration_sum": 0.0,
                }
            stats = model_stats[model]
            stats["total_requests"] += 1
            stats["total_tokens"] += entry.total_tokens
            stats["total_cost"] += entry.estimated_cost_usd
            stats["duration_sum"] += entry.duration_seconds

        result = []
        for model, stats in model_stats.items():
            avg_duration = stats["duration_sum"] / stats["total_requests"] if stats["total_requests"] > 0 else 0
            tokens_per_sec = (stats["total_tokens"] / stats["total_requests"]) / avg_duration if avg_duration > 0 else 0
            cost_per_k = (stats["total_cost"] / (stats["total_tokens"] / 1000)) if stats["total_tokens"] > 0 else 0
            result.append({
                "model": model, "requests": stats["total_requests"],
                "total_tokens": stats["total_tokens"],
                "total_cost": round(stats["total_cost"], 8),
                "avg_duration_sec": round(avg_duration, 2),
                "tokens_per_sec": round(tokens_per_sec, 2),
                "cost_per_k_tokens": round(cost_per_k, 8),
            })
        result.sort(key=lambda x: x["total_cost"], reverse=True)
        return result

    def get_budget_alerts(self, daily_budget: float = 5.0, monthly_budget: float = 100.0) -> list[dict]:
        """Check if current usage exceeds budget thresholds."""
        alerts = []
        daily_stats = self.storage.get_daily_stats(days=30)
        if daily_stats:
            avg_daily = sum(d["cost"] for d in daily_stats) / len(daily_stats)
            if avg_daily > daily_budget:
                alerts.append({
                    "type": "daily_budget_exceeded",
                    "message": f"Average daily cost (${avg_daily:.2f}) exceeds daily budget (${daily_budget:.2f})",
                    "severity": "high",
                    "avg_daily_cost": round(avg_daily, 2),
                    "budget": daily_budget,
                })

        monthly_summary = self.storage.get_cost_summary(
            start_date=datetime.now(timezone.utc) - timedelta(days=30)
        )
        if monthly_summary.total_cost_usd > monthly_budget:
            alerts.append({
                "type": "monthly_budget_exceeded",
                "message": f"Monthly cost (${monthly_summary.total_cost_usd:.2f}) exceeds monthly budget (${monthly_budget:.2f})",
                "severity": "critical",
                "monthly_cost": round(monthly_summary.total_cost_usd, 2),
                "budget": monthly_budget,
            })

        for model_name, model_info in MODEL_CATALOG.items():
            if model_info.input_price_per_million > 10.0 or model_info.output_price_per_million > 50.0:
                alerts.append({
                    "type": "expensive_model",
                    "message": f"Model '{model_name}' is expensive (${model_info.input_price_per_million}/M input, ${model_info.output_price_per_million}/M output)",
                    "severity": "medium",
                    "model": model_name,
                    "pricing": f"${model_info.input_price_per_million}/M in, ${model_info.output_price_per_million}/M out",
                })
        return alerts
