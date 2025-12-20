'use client';

import { createContext, useContext, useState, ReactNode } from 'react';
import { WeekSelection } from '@/types';

interface WeekContextType {
  gameWeek: WeekSelection | null;
  setGameWeek: (week: WeekSelection | null) => void;
}

const WeekContext = createContext<WeekContextType | undefined>(undefined);

export function WeekProvider({ children }: { children: ReactNode }) {
  const [gameWeek, setGameWeek] = useState<WeekSelection | null>(null);

  return (
    <WeekContext.Provider value={{ gameWeek, setGameWeek }}>
      {children}
    </WeekContext.Provider>
  );
}

export function useWeekContext() {
  const context = useContext(WeekContext);
  if (context === undefined) {
    throw new Error('useWeekContext must be used within a WeekProvider');
  }
  return context;
}
