'use client';

import { feedbackUrl } from '../../public/feedback.js';

export function FeedbackLink() {
  const updateLink = (event: React.SyntheticEvent<HTMLAnchorElement>) => {
    event.currentTarget.href = feedbackUrl(window);
  };
  return (
    <footer className="feedback-footer">
      <a data-analytics-event="feedback_opened" href="mailto:ben.shoemaker.xyz@gmail.com?subject=NFL%20Win%20Delta%20feedback"
        onClick={updateLink} onFocus={updateLink} onMouseEnter={updateLink}>
        Send feedback
      </a>
      <span>Opens your email app with page details and available session IDs.</span>
    </footer>
  );
}
