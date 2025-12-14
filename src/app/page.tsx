export default function Home() {
  return (
    <div className="container mx-auto px-6 py-12">
      <div className="text-center">
        <h1 className="font-display text-6xl tracking-wide text-text-primary mb-4">
          NFL Game Explainer
        </h1>
        <p className="font-condensed text-xl text-text-secondary uppercase tracking-wider">
          Live Game Analysis Dashboard
        </p>
      </div>

      <div className="mt-12 max-w-2xl mx-auto">
        <div className="bg-bg-card border border-border-subtle rounded-2xl p-8">
          <h2 className="font-display text-2xl tracking-wide text-gold mb-4">
            Coming Soon
          </h2>
          <p className="font-body text-text-secondary leading-relaxed">
            Real-time NFL game analysis with advanced statistics, win probability tracking,
            and AI-powered game summaries. Check back during game time for live updates.
          </p>
        </div>
      </div>
    </div>
  );
}
