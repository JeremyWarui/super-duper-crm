import { PageHeader, useSlottedHeader } from "@/components/layout/AppPage";

// A kit page's frosted header: the menu group, the title and the page's actions.
export default function WsHeader(props) {
  const header = useSlottedHeader(<PageHeader {...props} />);
  return header.slotted ? header.rendered : <PageHeader {...props} />;
}

export const KitLoading = () => <p className="text-muted-foreground">Loading…</p>;
export const KitError = ({ error }) => <p role="alert" className="font-semibold text-destructive">{error.message}</p>;
