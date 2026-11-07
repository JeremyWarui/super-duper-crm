// Contributions paid in from the campaign's website; the candidate or the manager confirms each
// M-Pesa code a payer reported against the campaign's M-Pesa statement.
import PaymentsInTable from "@/components/PaymentsInTable";
import WsHeader from "./WsHeader";

export default function Contributions({ campaign }) {
  return (
    <>
      <WsHeader context="Money" title="Contributions" sub="Given on the website by M-Pesa. Confirm each code against your M-Pesa statement." />
      <PaymentsInTable campaignId={campaign.id} />
    </>
  );
}
