from __future__ import annotations

from analytics_service.domain.entities.team_statistics import TeamStatistics


class StatisticsCalculator:
    """Pure calculation boundary; incomplete observations must not count as losses."""

    def win_rate(self, statistics: TeamStatistics) -> float | None:
        raise NotImplementedError("Define eligible result denominator and zero-sample behavior")
