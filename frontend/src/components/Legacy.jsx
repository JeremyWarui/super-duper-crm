// The root of a page not yet moved onto the UI kit; index.css styles only what is inside it.
export default function Legacy({ children }) {
  return <div className="legacy">{children}</div>;
}
