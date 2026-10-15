// Shown the moment a link is clicked, while the next page's data loads,
// so a click is answered at once instead of after the server replies.
export default function Loading() {
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
