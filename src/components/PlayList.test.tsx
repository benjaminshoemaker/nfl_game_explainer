import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PlayList } from './PlayList';

describe('PlayList', () => {
  it('shows end spot on every card and replaces kickoff return yards with end spot in Drive Starts', () => {
    render(
      <PlayList
        plays={[
          {
            type: 'Kickoff',
            text: 'Kickoff return to LAR 29.',
            yards: 28,
            quarter: 1,
            clock: '15:00',
            end_pos: 'LAR 29',
          },
        ]}
        teamAbbr="LAR"
        teamSecondary="#FFA300"
        teamTextColor="#FFA300"
        opponentTextColor="#4DC3FF"
        side="home"
        category="Drive Starts"
      />
    );

    expect(screen.getByText('LAR 29')).toBeInTheDocument();
    const ownBadge = screen.getByText('Own 29 Yard Line');
    expect(ownBadge).toBeInTheDocument();
    expect(ownBadge).toHaveStyle({ color: '#FFA300' });
    expect(screen.queryByText('+28 YDS')).not.toBeInTheDocument();
  });

  it('replaces punt yards with end spot in Drive Starts', () => {
    render(
      <PlayList
        plays={[
          {
            type: 'Punt',
            text: 'Punt to LAR 38.',
            yards: 31,
            quarter: 2,
            clock: '10:24',
            end_pos: 'LAR 38',
          },
        ]}
        teamAbbr="LAR"
        teamSecondary="#FFA300"
        teamTextColor="#FFA300"
        opponentTextColor="#4DC3FF"
        side="home"
        category="Drive Starts"
      />
    );

    expect(screen.getByText('LAR 38')).toBeInTheDocument();
    expect(screen.getByText('Own 38 Yard Line')).toBeInTheDocument();
    expect(screen.queryByText('+31 YDS')).not.toBeInTheDocument();
  });

  it('replaces interception return yards with end spot in Drive Starts', () => {
    render(
      <PlayList
        plays={[
          {
            type: 'Pass',
            text: 'Intercepted and returned to SEA 1.',
            yards: 56,
            quarter: 3,
            clock: '6:30',
            end_pos: 'SEA 1',
          },
        ]}
        teamAbbr="LAR"
        teamSecondary="#FFA300"
        teamTextColor="#FFA300"
        opponentTextColor="#4DC3FF"
        side="home"
        category="Drive Starts"
      />
    );

    expect(screen.getByText('SEA 1')).toBeInTheDocument();
    const oppBadge = screen.getByText('Opp 1 Yard Line');
    expect(oppBadge).toBeInTheDocument();
    expect(oppBadge).toHaveStyle({ color: '#4DC3FF' });
    expect(screen.queryByText('+56 YDS')).not.toBeInTheDocument();
  });

  it('shows end spot and preserves kickoff return yards outside Drive Starts', () => {
    render(
      <PlayList
        plays={[
          {
            type: 'Kickoff',
            text: 'Kickoff return to LAR 29.',
            yards: 28,
            quarter: 1,
            clock: '15:00',
            end_pos: 'LAR 29',
          },
        ]}
        teamAbbr="LAR"
        teamSecondary="#FFA300"
        teamTextColor="#FFA300"
        opponentTextColor="#4DC3FF"
        side="home"
        category="All Plays"
      />
    );

    expect(screen.getByText('LAR 29')).toBeInTheDocument();
    expect(screen.getByText('+28 YDS')).toBeInTheDocument();
    expect(screen.queryByText('Own 29 Yard Line')).not.toBeInTheDocument();
  });

  it('preserves penalty yards in Penalty Yards category even for kickoff plays', () => {
    render(
      <PlayList
        plays={[
          {
            type: 'Kickoff',
            text: 'Kickoff return with penalty enforced.',
            yards: -10,
            quarter: 1,
            clock: '15:00',
            end_pos: 'SEA 20',
          },
        ]}
        teamAbbr="SEA"
        teamSecondary="#4DC3FF"
        teamTextColor="#4DC3FF"
        opponentTextColor="#FFA300"
        side="home"
        category="Penalty Yards"
      />
    );

    expect(screen.getByText('SEA 20')).toBeInTheDocument();
    expect(screen.getByText('-10 yards')).toBeInTheDocument();
    expect(screen.queryByText('Own 20 Yard Line')).not.toBeInTheDocument();
  });

  it('shows end spot and preserves yards for non-kickoff plays', () => {
    render(
      <PlayList
        plays={[
          {
            type: 'Pass',
            text: 'Pass complete to LAR 40 for 12 yards.',
            yards: 12,
            quarter: 1,
            clock: '14:12',
            end_pos: 'LAR 40',
          },
        ]}
        teamAbbr="SEA"
        teamSecondary="#4DC3FF"
        teamTextColor="#4DC3FF"
        opponentTextColor="#FFA300"
        side="away"
        category="All Plays"
      />
    );

    expect(screen.getByText('LAR 40')).toBeInTheDocument();
    expect(screen.getByText('+12 YDS')).toBeInTheDocument();
  });
});
