import { useWardOptions } from "./helpers";
import RegisterSupporterForm from "./RegisterSupporterForm";
import WsHeader from "./WsHeader";

export default function Register({ campaign }) {
  const wardOptions = useWardOptions(campaign.id);
  return (
    <>
      <WsHeader context="My work" title="Register a supporter" sub="Quick capture in the field." />
      <RegisterSupporterForm campaignId={campaign.id} wardOptions={wardOptions} byCentre={campaign.operational_grain === "centre"} />
    </>
  );
}
