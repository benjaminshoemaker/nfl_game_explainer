import Link from 'next/link';
import styles from '@/components/StateScreens.module.css';

export default function NotFound() {
  return <div className={styles.screen}>
    <header className={styles.header}>GAME<span>/</span>EXPLAINED</header>
    <main className={styles.body}>
      <div className={styles.kicker}>404 / Page not found</div>
      <h1>That page isn’t here.</h1>
      <p>The page may have moved, or its address may be incorrect.</p>
      <div className={styles.actions}><Link href="/">Back to games</Link></div>
    </main>
  </div>;
}
