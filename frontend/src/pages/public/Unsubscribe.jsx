// /unsubscribe/:code: stop the site's news for the contact this link came with.
import { useParams } from "react-router-dom";
import { useUnsubscribe } from "@/api/hooks";
import LinkAction from "@/components/LinkAction";
import { useCopy } from "@/copy";

export default function Unsubscribe() {
  const { code } = useParams();
  const copy = useCopy();
  return (
    <LinkAction action={useUnsubscribe(code)} heading="Unsubscribe" note={copy.unsubscribe} label="Unsubscribe" busyLabel="Unsubscribing…" variant="primary" />
  );
}
