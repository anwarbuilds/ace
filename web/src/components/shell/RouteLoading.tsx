// Shown the moment a link is clicked, while the next page's data loads,
// so a click is answered at once instead of after the server replies.
// Every workspace route uses it through its loading.tsx: without one,
// Next waits for the whole server render before showing anything, and
// a slow page looks like a click that was ignored.
export function RouteLoading() {
  return (
    <div className="page" aria-busy="true" aria-label="Loading">
      <div className="sk-page">
        <span className="sk-line sk-h" />
        <span className="sk-line" />
        <span className="sk-block" />
        <span className="sk-block" />
        <span className="sk-block" />
      </div>
    </div>
  );
}
