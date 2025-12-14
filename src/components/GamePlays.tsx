'use client';

import { useState, useMemo } from 'react';
import { PlayDetail, TeamMeta } from '@/types';
import { PlayList } from './PlayList';
import { PlayTabs } from './PlayTabs';
import { getTeamColors } from '@/lib/teamColors';

interface GamePlaysProps {
  expandedDetails: Record<string, Record<string, PlayDetail[]>>;
  teamMeta: TeamMeta[];
}

// Map of internal category keys to display labels
const CATEGORY_LABELS: Record<string, string> = {
  'Turnovers': 'Turnovers',
  'Explosive Plays': 'Explosive',
  'Non-Offensive Scores': 'Non-Off TDs',
  'Scoring Plays': 'Scoring',
  'Key Plays': 'Key Plays',
};

export function GamePlays({ expandedDetails, teamMeta }: GamePlaysProps) {
  // Get available categories from the data
  const categories = useMemo(() => {
    const cats = Object.keys(expandedDetails);
    // Sort to put most important first
    const order = ['Turnovers', 'Explosive Plays', 'Non-Offensive Scores', 'Scoring Plays', 'Key Plays'];
    return cats.sort((a, b) => {
      const aIdx = order.indexOf(a);
      const bIdx = order.indexOf(b);
      if (aIdx === -1 && bIdx === -1) return a.localeCompare(b);
      if (aIdx === -1) return 1;
      if (bIdx === -1) return -1;
      return aIdx - bIdx;
    });
  }, [expandedDetails]);

  const [activeTab, setActiveTab] = useState(categories[0] || '');

  const away = teamMeta.find((t) => t.homeAway === 'away');
  const home = teamMeta.find((t) => t.homeAway === 'home');

  if (!away || !home || categories.length === 0) {
    return (
      <div className="bg-bg-card rounded-2xl border border-border-subtle p-6 text-center">
        <p className="text-text-muted font-body">No play data available</p>
      </div>
    );
  }

  const awayColors = getTeamColors(away.abbr);
  const homeColors = getTeamColors(home.abbr);

  // Build tabs with counts
  const tabs = categories.map((cat) => {
    const catData = expandedDetails[cat] || {};
    const awayPlays = catData[away.abbr] || [];
    const homePlays = catData[home.abbr] || [];
    const totalCount = awayPlays.length + homePlays.length;

    return {
      id: cat,
      label: CATEGORY_LABELS[cat] || cat,
      count: totalCount,
    };
  });

  // Get plays for current category
  const currentCategoryData = expandedDetails[activeTab] || {};
  const awayPlays = currentCategoryData[away.abbr] || [];
  const homePlays = currentCategoryData[home.abbr] || [];

  return (
    <div className="bg-bg-card rounded-2xl border border-border-subtle overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-bg-elevated border-b border-border-subtle">
        <h3 className="font-display text-lg tracking-wide text-text-primary">
          Key Plays
        </h3>
        <p className="font-condensed text-xs text-text-muted uppercase tracking-wider mt-1">
          Game-changing moments
        </p>
      </div>

      {/* Tabs */}
      <div className="p-3 border-b border-border-subtle">
        <PlayTabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />
      </div>

      {/* Team sections */}
      <div className="divide-y divide-border-subtle">
        {/* Away team plays */}
        <div className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: awayColors.primary }}
            />
            <span className="font-condensed text-sm uppercase tracking-wider text-text-secondary">
              {away.abbr}
            </span>
            <span className="text-xs text-text-muted">
              ({awayPlays.length})
            </span>
          </div>
          <PlayList
            plays={awayPlays}
            teamAbbr={away.abbr}
            teamColor={awayColors.primary}
          />
        </div>

        {/* Home team plays */}
        <div className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: homeColors.primary }}
            />
            <span className="font-condensed text-sm uppercase tracking-wider text-text-secondary">
              {home.abbr}
            </span>
            <span className="text-xs text-text-muted">
              ({homePlays.length})
            </span>
          </div>
          <PlayList
            plays={homePlays}
            teamAbbr={home.abbr}
            teamColor={homeColors.primary}
          />
        </div>
      </div>
    </div>
  );
}
