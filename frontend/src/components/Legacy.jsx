// The root of a page not yet moved onto the UI kit; index.css styles only what is inside it.
// `bare` drops the root's full-screen height and ground, for a legacy form over a kit page.

const BARE = { minHeight: 0, background: "transparent" };

export default function Legacy({ children, bare }) {
  return <div className="legacy" style={bare ? BARE : undefined}>{children}</div>;
}
