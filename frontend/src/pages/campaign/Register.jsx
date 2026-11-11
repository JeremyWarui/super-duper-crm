import { unitOf, useWardOptions } from "./helpers";
import RegisterSupporterForm from "./RegisterSupporterForm";
import { SlottedHeader } from "@/components/layout/AppPage";

export default function Register({ campaign }) {
  const wardOptions = useWardOptions(campaign.id);
  return (
    <>
      <SlottedHeader context="My work" title="Register a supporter" sub="Quick capture in the field." />
      <RegisterSupporterForm campaignId={campaign.id} wardOptions={wardOptions} byCentre={unitOf(campaign).byCentre} />
    </>
  );
}
