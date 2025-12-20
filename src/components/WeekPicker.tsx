'use client';

import { WeekSelection } from '@/types';
import {
  WEEK_OPTIONS,
  getRegularSeasonOptions,
  getPlayoffOptions,
  weekToUrlParam,
} from '@/lib/weekUtils';

interface WeekPickerProps {
  currentWeek: WeekSelection;
  onWeekChange: (week: WeekSelection) => void;
}

export function WeekPicker({ currentWeek, onWeekChange }: WeekPickerProps) {
  const regularOptions = getRegularSeasonOptions();
  const playoffOptions = getPlayoffOptions();

  const currentValue = weekToUrlParam(currentWeek);

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    const option = WEEK_OPTIONS.find((w) => weekToUrlParam(w) === value);
    if (option) {
      onWeekChange({
        weekNumber: option.weekNumber,
        seasonType: option.seasonType,
      });
    }
  };

  return (
    <div className="relative inline-block">
      <select
        value={currentValue}
        onChange={handleChange}
        className="
          appearance-none
          bg-bg-elevated
          border border-border-subtle
          rounded-lg
          px-4 py-2 pr-8
          font-condensed text-sm uppercase tracking-wider
          text-text-primary
          cursor-pointer
          hover:border-gold/50
          focus:outline-none focus:border-gold
          transition-colors
        "
      >
        <optgroup label="Regular Season">
          {regularOptions.map((option) => (
            <option
              key={option.value}
              value={option.value}
              className="bg-bg-card text-text-primary"
            >
              {option.label}
            </option>
          ))}
        </optgroup>
        <optgroup label="Playoffs">
          {playoffOptions.map((option) => (
            <option
              key={option.value}
              value={option.value}
              className="bg-bg-card text-text-primary"
            >
              {option.label}
            </option>
          ))}
        </optgroup>
      </select>
      {/* Dropdown arrow */}
      <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
        <svg
          className="w-4 h-4 text-text-muted"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </div>
    </div>
  );
}
