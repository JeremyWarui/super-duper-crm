import { PageTitle } from "../../components/ui";
import { useEvents } from "../../api/hooks";
import { Btn, ErrorMsg, Loading } from "./controls";
import EventList from "./EventList";

export default function Events({ campaign, role, onModal, mine }) {
  const events = useEvents(campaign.id);
  if (events.isLoading) return <Loading />; if (events.error) return <ErrorMsg error={events.error} />;
  return (<><PageTitle title={mine ? "My events" : "Events"} sub="Rallies and meetings, with mobilization counts." action={role !== "candidate" ? <Btn primary onClick={() => onModal({ type: "event" })}>Schedule event</Btn> : null} /><EventList events={events.data || []} showActions={role !== "candidate"} onRecord={(e) => onModal({ type: "record", event: e })} onInvite={(e) => onModal({ type: "invite", event: e })} onQr={role !== "candidate" ? (e) => onModal({ type: "qr", event: e }) : undefined} /></>);
}
