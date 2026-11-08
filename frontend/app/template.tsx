/** Re-mounts on every navigation, so each page fades in (opacity only under reduced motion). */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
