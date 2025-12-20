'use client';

import { useState, useMemo, useEffect } from 'react';
import { PlayDetail, TeamMeta } from '@/types';
import { PlayList } from './PlayList';
import { getTeamColorVars } from '@/lib/teamColors';
import Image from 'next/image';

interface GamePlaysProps {
  expandedDetails: Record<string, Record<string, PlayDetail[]>>;
  teamMeta: TeamMeta[];
  selectedCategory?: string;
}

type SortOption = 'chronological' | 'wp_impact';

// Map of internal category keys to display labels
const CATEGORY_OPTIONS = [
  { key: 'All Plays', label: 'All Plays' },
  { key: 'Explosive Plays', label: 'Explosive Plays' },
  { key: 'Turnovers', label: 'Turnovers' },
  { key: 'Points Per Trip (Inside 40)', label: 'Points Per Trip' },
  { key: 'Drive Starts', label: 'Drive Starts' },
  { key: 'Penalty Yards', label: 'Penalty Plays' },
  { key: 'Non-Offensive Points', label: 'Non-Offensive Points' },
];

export function GamePlays({ expandedDetails, teamMeta, selectedCategory }: GamePlaysProps) {
  const [activeCategory, setActiveCategory] = useState(selectedCategory || 'All Plays');
  const [sortBy, setSortBy] = useState<SortOption>('chronological');

  // Update active category when selectedCategory changes from parent
  useEffect(() => {
    if (selectedCategory) {
      setActiveCategory(selectedCategory);
    }
  }, [selectedCategory]);

  const away = teamMeta.find((t) => t.homeAway === 'away');
  const home = teamMeta.find((t) => t.homeAway === 'home');
  const awayId = away?.id;
  const homeId = home?.id;
  const awayAbbr = away?.abbr;
  const homeAbbr = home?.abbr;

  // Get available categories from the data
  const availableCategories = useMemo(() => {
    return CATEGORY_OPTIONS.filter((opt) => {
      const catData = expandedDetails[opt.key];
      return catData && (
        (catData[awayId || '']?.length || 0) +
        (catData[homeId || '']?.length || 0) > 0
      );
    });
  }, [expandedDetails, awayId, homeId]);

  // Get plays for current category - use team ID as key
  const { awayPlays, homePlays } = useMemo(() => {
    const currentCategoryData = expandedDetails[activeCategory] || {};
    const awayValues = awayId ? currentCategoryData[awayId] : undefined;
    const awayFallback = awayAbbr ? currentCategoryData[awayAbbr] : undefined;
    const homeValues = homeId ? currentCategoryData[homeId] : undefined;
    const homeFallback = homeAbbr ? currentCategoryData[homeAbbr] : undefined;

    return {
      awayPlays: awayValues || awayFallback || [],
      homePlays: homeValues || homeFallback || [],
    };
  }, [expandedDetails, activeCategory, awayId, awayAbbr, homeId, homeAbbr]);

  // Sort plays based on selected sort option
  const sortedAwayPlays = useMemo(() => {
    if (sortBy === 'chronological') {
      return awayPlays;
    }
    // Sort by absolute WP delta (largest impact first)
    return [...awayPlays].sort((a, b) => {
      const aDelta = Math.abs(a.probability?.awayDelta || 0);
      const bDelta = Math.abs(b.probability?.awayDelta || 0);
      return bDelta - aDelta;
    });
  }, [awayPlays, sortBy]);

  const sortedHomePlays = useMemo(() => {
    if (sortBy === 'chronological') {
      return homePlays;
    }
    // Sort by absolute WP delta (largest impact first)
    return [...homePlays].sort((a, b) => {
      const aDelta = Math.abs(a.probability?.homeDelta || 0);
      const bDelta = Math.abs(b.probability?.homeDelta || 0);
      return bDelta - aDelta;
    });
  }, [homePlays, sortBy]);

  if (!away || !home || availableCategories.length === 0) {
    return (
      <div className="bg-bg-card rounded-2xl border border-border-subtle p-6 text-center">
        <p className="text-text-muted font-body">No play data available</p>
      </div>
    );
  }

  const awayColors = getTeamColorVars(away.abbr);
  const homeColors = getTeamColorVars(home.abbr);

  return (
    <div className="bg-bg-card rounded-2xl border border-border-subtle overflow-hidden">
      {/* Header with filter */}
      <div className="px-6 py-4 bg-bg-elevated border-b border-border-subtle flex items-center justify-between">
        <div className="flex items-center gap-3">
          <svg
            className="w-5 h-5 text-text-muted"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
          <h3 className="font-display text-lg tracking-wider text-text-primary">
            KEY PLAYS
          </h3>
        </div>

        <div className="flex items-center gap-2">
          {/* Sort dropdown */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="appearance-none bg-bg-elevated border border-border-medium rounded-lg px-4 py-2 pr-10 font-body text-sm font-semibold text-text-primary cursor-pointer transition-all duration-200 hover:border-text-muted focus:outline-none focus:border-text-muted"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%239ca3af' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'right 0.75rem center',
            }}
          >
            <option value="chronological">By Time</option>
            <option value="wp_impact">By WP Impact</option>
          </select>

          {/* Category dropdown */}
          <select
            value={activeCategory}
            onChange={(e) => setActiveCategory(e.target.value)}
            className="appearance-none bg-bg-elevated border border-border-medium rounded-lg px-4 py-2 pr-10 font-body text-sm font-semibold text-text-primary cursor-pointer transition-all duration-200 hover:border-text-muted focus:outline-none focus:border-text-muted"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%239ca3af' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'right 0.75rem center',
            }}
          >
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.key} value={opt.key}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Two-column plays grid */}
      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Away Column */}
          <div className="plays-column">
            {/* Column Header */}
            <div
              className="flex items-center gap-3 mb-4 pb-3 border-b-2"
              style={{ borderColor: awayColors.secondary }}
            >
              <div className="relative w-7 h-7 flex-shrink-0">
                <Image
                  src={awayColors.logo}
                  alt={away.abbr}
                  fill
                  className="object-contain"
                />
              </div>
              <span
                className="font-display text-sm px-3 py-1.5 rounded-md tracking-wide"
                style={{
                  background: awayColors.primary,
                  color: awayColors.secondary,
                }}
              >
                {away.abbr}
              </span>
              <span className="font-condensed font-semibold text-sm uppercase tracking-wider text-text-secondary">
                {away.name}
              </span>
              <span className="ml-auto font-condensed text-xs font-medium text-text-muted uppercase tracking-wider">
                {awayPlays.length} plays
              </span>
            </div>

            <PlayList
              plays={sortedAwayPlays}
              teamAbbr={away.abbr}
              teamSecondary={awayColors.secondary}
              teamTextColor={awayColors.text}
              opponentTextColor={homeColors.text}
              side="away"
              category={activeCategory}
            />
          </div>

          {/* Home Column */}
          <div className="plays-column">
            {/* Column Header */}
            <div
              className="flex items-center gap-3 mb-4 pb-3 border-b-2"
              style={{ borderColor: homeColors.secondary }}
            >
              <div className="relative w-7 h-7 flex-shrink-0">
                <Image
                  src={homeColors.logo}
                  alt={home.abbr}
                  fill
                  className="object-contain"
                />
              </div>
              <span
                className="font-display text-sm px-3 py-1.5 rounded-md tracking-wide"
                style={{
                  background: homeColors.primary,
                  color: homeColors.secondary,
                }}
              >
                {home.abbr}
              </span>
              <span className="font-condensed font-semibold text-sm uppercase tracking-wider text-text-secondary">
                {home.name}
              </span>
              <span className="ml-auto font-condensed text-xs font-medium text-text-muted uppercase tracking-wider">
                {homePlays.length} plays
              </span>
            </div>

            <PlayList
              plays={sortedHomePlays}
              teamAbbr={home.abbr}
              teamSecondary={homeColors.secondary}
              teamTextColor={homeColors.text}
              opponentTextColor={awayColors.text}
              side="home"
              category={activeCategory}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
