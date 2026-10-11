export function greeting(hour = new Date().getHours()) {
  return hour < 12
    ? 'Good morning'
    : hour < 17
      ? 'Good afternoon'
      : 'Good evening';
}

export function relativeTime(timestamp, now = Date.now()) {
  const seconds = Math.max(
    0,
    Math.floor((now - timestamp * 1000) / 1000),
  );

  if (seconds < 60) return 'Just now';

  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}m ago`;
  }

  if (seconds < 86400) {
    return `${Math.floor(seconds / 3600)}h ago`;
  }

  if (seconds < 604800) {
    return `${Math.floor(seconds / 86400)}d ago`;
  }

  return new Date(timestamp * 1000).toLocaleDateString(
    undefined,
    { month: 'short', day: 'numeric' },
  );
}

export function filterActivity(activity, query, type) {
  const text = query.trim().toLocaleLowerCase();

  return activity.filter((item) => (
    (type === 'all' || item.type === type)
    && (
      !text
      || `${item.title} ${item.summary || ''} ${item.planId || ''}`
        .toLocaleLowerCase()
        .includes(text)
    )
  ));
}