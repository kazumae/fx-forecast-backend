"""
Priority Ranking Engine

Prioritizes multiple entry signals when they occur simultaneously,
ensuring optimal capital allocation, risk distribution, and profit maximization.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Tuple, Set, Optional
import asyncio
from collections import defaultdict

from src.domain.models.priority_ranking import (
    EntrySignal, ExistingPosition, PriorityRankingResult, 
    PrioritizedSignal, ExcludedSignal, CorrelationInfo,
    PriorityRankingConfig, ExclusionReason, SignalStatus
)
from src.domain.models.scoring import ConfidenceLevel, PatternType


class PriorityRankingEngine:
    """Main priority ranking engine for signal prioritization"""
    
    def __init__(self, config: PriorityRankingConfig = None):
        """Initialize with configuration"""
        self.config = config or PriorityRankingConfig()
    
    async def rank_signals(
        self,
        signals: List[EntrySignal],
        existing_positions: List[ExistingPosition] = None
    ) -> PriorityRankingResult:
        """Rank signals by priority with correlation detection and risk management"""
        existing_positions = existing_positions or []
        
        # Step 1: Pre-filter signals by quality
        quality_filtered_signals = self._filter_by_quality(signals)
        
        # Step 2: Detect correlations
        correlations = await self._detect_correlations(quality_filtered_signals)
        
        # Step 3: Remove correlated signals
        correlation_filtered_signals, correlation_excluded = self._remove_correlated_signals(
            quality_filtered_signals, correlations
        )
        
        # Step 4: Apply position limits
        position_filtered_signals, position_excluded = self._apply_position_limits(
            correlation_filtered_signals, existing_positions
        )
        
        # Step 5: Calculate priority scores and rank
        prioritized_signals = await self._calculate_priority_scores(position_filtered_signals)
        
        # Step 6: Final ranking
        final_prioritized = self._apply_final_ranking(prioritized_signals)
        
        # Combine all excluded signals
        all_excluded = correlation_excluded + position_excluded
        
        return PriorityRankingResult(
            prioritized_signals=final_prioritized,
            excluded_signals=all_excluded,
            timestamp=datetime.utcnow()
        )
    
    def _filter_by_quality(self, signals: List[EntrySignal]) -> List[EntrySignal]:
        """Filter signals by minimum quality thresholds"""
        filtered = []
        
        for signal in signals:
            # Check minimum composite score
            if signal.composite_score < self.config.min_composite_score:
                continue
            
            # Check minimum risk-reward ratio
            if signal.risk_reward_ratio < self.config.min_risk_reward_ratio:
                continue
            
            filtered.append(signal)
        
        return filtered
    
    async def _detect_correlations(self, signals: List[EntrySignal]) -> List[CorrelationInfo]:
        """Detect correlations between signals"""
        correlations = []
        
        for i, signal1 in enumerate(signals):
            for signal2 in signals[i + 1:]:
                correlation = await self._check_signal_correlation(signal1, signal2)
                if correlation:
                    correlations.append(correlation)
        
        return correlations
    
    async def _check_signal_correlation(
        self, 
        signal1: EntrySignal, 
        signal2: EntrySignal
    ) -> Optional[CorrelationInfo]:
        """Check if two signals are correlated"""
        # Only check same symbol
        if signal1.symbol != signal2.symbol:
            return None
        
        # Same direction proximity check
        direction1 = "long" if signal1.entry_price < signal1.take_profit else "short"
        direction2 = "long" if signal2.entry_price < signal2.take_profit else "short"
        
        if direction1 == direction2:
            distance = abs(float(signal1.entry_price - signal2.entry_price))
            if distance <= self.config.same_direction_correlation_threshold_pips:
                return CorrelationInfo(
                    signal1_id=signal1.signal_id,
                    signal2_id=signal2.signal_id,
                    correlation_type=ExclusionReason.CORRELATION_SAME_DIRECTION,
                    distance_pips=distance,
                    description=f"Same direction signals within {distance:.1f} pips"
                )
        
        # Stop loss overlap check (opposite directions)
        if direction1 != direction2:
            sl_distance = abs(float(signal1.stop_loss - signal2.stop_loss))
            if sl_distance <= self.config.stop_loss_overlap_threshold_pips:
                return CorrelationInfo(
                    signal1_id=signal1.signal_id,
                    signal2_id=signal2.signal_id,
                    correlation_type=ExclusionReason.CORRELATION_STOP_LOSS_OVERLAP,
                    distance_pips=sl_distance,
                    description=f"Stop loss overlap: {sl_distance:.1f} pips apart"
                )
        
        return None
    
    def _remove_correlated_signals(
        self,
        signals: List[EntrySignal],
        correlations: List[CorrelationInfo]
    ) -> Tuple[List[EntrySignal], List[ExcludedSignal]]:
        """Remove correlated signals, keeping the best one from each group"""
        if not correlations:
            return signals, []
        
        # Build correlation groups
        correlation_groups = self._build_correlation_groups(signals, correlations)
        
        filtered_signals = []
        excluded_signals = []
        
        processed_signal_ids = set()
        
        for group in correlation_groups:
            if len(group) == 1:
                # No correlation, keep the signal
                filtered_signals.append(group[0])
                processed_signal_ids.add(group[0].signal_id)
            else:
                # Multiple correlated signals, keep the best one
                best_signal = self._select_best_signal_from_group(group)
                filtered_signals.append(best_signal)
                processed_signal_ids.add(best_signal.signal_id)
                
                # Exclude the rest
                for signal in group:
                    if signal.signal_id != best_signal.signal_id:
                        excluded_signals.append(ExcludedSignal(
                            signal=signal,
                            exclusion_reason=ExclusionReason.CORRELATION_SAME_DIRECTION,
                            exclusion_details=f"Correlated with higher priority signal {best_signal.signal_id}",
                            correlations=[c for c in correlations if signal.signal_id in [c.signal1_id, c.signal2_id]]
                        ))
                        processed_signal_ids.add(signal.signal_id)
        
        # Add any signals not in correlation groups
        for signal in signals:
            if signal.signal_id not in processed_signal_ids:
                filtered_signals.append(signal)
        
        return filtered_signals, excluded_signals
    
    def _build_correlation_groups(
        self,
        signals: List[EntrySignal],
        correlations: List[CorrelationInfo]
    ) -> List[List[EntrySignal]]:
        """Build groups of correlated signals"""
        signal_dict = {s.signal_id: s for s in signals}
        
        # Build adjacency list
        adjacency = defaultdict(set)
        for corr in correlations:
            adjacency[corr.signal1_id].add(corr.signal2_id)
            adjacency[corr.signal2_id].add(corr.signal1_id)
        
        # Find connected components (correlation groups)
        visited = set()
        groups = []
        
        for signal_id in signal_dict:
            if signal_id not in visited:
                group = []
                self._dfs_correlation_group(signal_id, adjacency, visited, group)
                groups.append([signal_dict[sid] for sid in group])
        
        return groups
    
    def _dfs_correlation_group(
        self,
        signal_id: str,
        adjacency: Dict[str, Set[str]],
        visited: Set[str],
        group: List[str]
    ):
        """DFS to find correlation group"""
        visited.add(signal_id)
        group.append(signal_id)
        
        for neighbor_id in adjacency[signal_id]:
            if neighbor_id not in visited:
                self._dfs_correlation_group(neighbor_id, adjacency, visited, group)
    
    def _select_best_signal_from_group(self, group: List[EntrySignal]) -> EntrySignal:
        """Select the best signal from a correlation group"""
        # Sort by priority: confidence level > RR ratio > composite score > pattern complexity
        return max(group, key=lambda s: (
            self.config.confidence_level_weights[s.confidence_level],
            s.risk_reward_ratio,
            s.composite_score,
            self.config.pattern_complexity_scores[s.pattern_type]
        ))
    
    def _apply_position_limits(
        self,
        signals: List[EntrySignal],
        existing_positions: List[ExistingPosition]
    ) -> Tuple[List[EntrySignal], List[ExcludedSignal]]:
        """Apply position limits and check conflicts with existing positions"""
        # Count existing positions by direction
        existing_long = len([p for p in existing_positions if p.direction == "long"])
        existing_short = len([p for p in existing_positions if p.direction == "short"])
        
        filtered_signals = []
        excluded_signals = []
        
        new_long_count = 0
        new_short_count = 0
        
        # Sort signals by priority for fair allocation
        sorted_signals = sorted(signals, key=lambda s: (
            -self.config.confidence_level_weights[s.confidence_level],
            -s.risk_reward_ratio,
            -s.composite_score
        ))
        
        for signal in sorted_signals:
            direction = "long" if signal.entry_price < signal.take_profit else "short"
            
            # Check total position limit
            total_existing = len(existing_positions)
            total_new = len(filtered_signals)
            if total_existing + total_new >= self.config.max_total_positions:
                excluded_signals.append(ExcludedSignal(
                    signal=signal,
                    exclusion_reason=ExclusionReason.POSITION_LIMIT_EXCEEDED,
                    exclusion_details=f"Total position limit ({self.config.max_total_positions}) exceeded"
                ))
                continue
            
            # Check same direction limit
            if direction == "long":
                if existing_long + new_long_count >= self.config.max_positions_same_direction:
                    excluded_signals.append(ExcludedSignal(
                        signal=signal,
                        exclusion_reason=ExclusionReason.POSITION_LIMIT_EXCEEDED,
                        exclusion_details=f"Long position limit ({self.config.max_positions_same_direction}) exceeded"
                    ))
                    continue
                new_long_count += 1
            else:
                if existing_short + new_short_count >= self.config.max_positions_same_direction:
                    excluded_signals.append(ExcludedSignal(
                        signal=signal,
                        exclusion_reason=ExclusionReason.POSITION_LIMIT_EXCEEDED,
                        exclusion_details=f"Short position limit ({self.config.max_positions_same_direction}) exceeded"
                    ))
                    continue
                new_short_count += 1
            
            filtered_signals.append(signal)
        
        return filtered_signals, excluded_signals
    
    async def _calculate_priority_scores(self, signals: List[EntrySignal]) -> List[EntrySignal]:
        """Calculate priority scores for signals"""
        for signal in signals:
            # Base score from confidence level
            confidence_weight = self.config.confidence_level_weights[signal.confidence_level]
            
            # Risk-reward component (normalized)
            rr_component = min(signal.risk_reward_ratio / 3.0, 1.0)  # Cap at 3:1
            
            # Composite score component (normalized)
            score_component = signal.composite_score / 100.0
            
            # Pattern complexity component
            complexity_component = self.config.pattern_complexity_scores[signal.pattern_type]
            
            # Time decay component (if enabled)
            time_decay = 1.0
            if self.config.enable_time_decay:
                age_minutes = (datetime.utcnow() - signal.timestamp).total_seconds() / 60
                time_decay = max(0.1, 1.0 - (age_minutes * self.config.time_decay_factor_per_minute))
            
            # Calculate final priority score
            priority_score = (
                confidence_weight * 0.4 +
                rr_component * 0.3 +
                score_component * 0.2 +
                complexity_component * 0.1
            ) * time_decay
            
            # Store priority score in signal metadata
            if not hasattr(signal, '_priority_score'):
                signal._priority_score = priority_score
        
        return signals
    
    def _apply_final_ranking(self, signals: List[EntrySignal]) -> List[PrioritizedSignal]:
        """Apply final ranking and create prioritized signals"""
        # Sort by priority score
        sorted_signals = sorted(signals, key=lambda s: s._priority_score, reverse=True)
        
        prioritized = []
        
        for rank, signal in enumerate(sorted_signals, 1):
            # Generate ranking reasons
            reasons = self._generate_ranking_reasons(signal, rank)
            
            prioritized.append(PrioritizedSignal(
                signal=signal,
                priority_rank=rank,
                priority_score=signal._priority_score,
                ranking_reasons=reasons
            ))
        
        return prioritized
    
    def _generate_ranking_reasons(self, signal: EntrySignal, rank: int) -> List[str]:
        """Generate human-readable ranking reasons"""
        reasons = []
        
        # Confidence level reason
        confidence_desc = {
            ConfidenceLevel.HIGH: "高信頼度",
            ConfidenceLevel.MEDIUM: "中信頼度", 
            ConfidenceLevel.LOW: "低信頼度"
        }
        reasons.append(f"{confidence_desc[signal.confidence_level]} ({signal.confidence_level.value})")
        
        # Risk-reward reason
        if signal.risk_reward_ratio >= 2.0:
            reasons.append(f"優秀なRR比 (1:{signal.risk_reward_ratio:.1f})")
        elif signal.risk_reward_ratio >= 1.5:
            reasons.append(f"良好なRR比 (1:{signal.risk_reward_ratio:.1f})")
        else:
            reasons.append(f"RR比 (1:{signal.risk_reward_ratio:.1f})")
        
        # Composite score reason
        if signal.composite_score >= 80:
            reasons.append(f"高スコア ({signal.composite_score:.0f}点)")
        elif signal.composite_score >= 70:
            reasons.append(f"良好スコア ({signal.composite_score:.0f}点)")
        else:
            reasons.append(f"スコア ({signal.composite_score:.0f}点)")
        
        # Pattern complexity
        pattern_desc = {
            PatternType.TREND_CONTINUATION: "トレンド継続 (シンプル)",
            PatternType.V_SHAPE_REVERSAL: "V字反転",
            PatternType.FALSE_BREAKOUT: "偽ブレイクアウト",
            PatternType.EMA_SQUEEZE: "EMAスクイーズ (複雑)"
        }
        reasons.append(pattern_desc.get(signal.pattern_type, signal.pattern_type.value))
        
        return reasons