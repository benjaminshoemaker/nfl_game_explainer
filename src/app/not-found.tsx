import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-bg-deep flex items-center justify-center">
      <div className="text-center space-y-4 max-w-md px-6">
        <div className="w-20 h-20 rounded-full bg-gold/20 flex items-center justify-center mx-auto">
          <span className="font-display text-4xl text-gold">404</span>
        </div>

        <h1 className="font-display text-3xl tracking-wide text-text-primary">
          Page Not Found
        </h1>

        <p className="font-body text-text-secondary leading-relaxed">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>

        <Link
          href="/"
          className="inline-block px-6 py-2 bg-gold text-bg-deep font-condensed uppercase tracking-wider rounded-lg hover:bg-gold/90 transition-colors"
        >
          Back to Games
        </Link>
      </div>
    </div>
  );
}
