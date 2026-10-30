import { PageTitle } from "../../components/ui";
import { useWardOptions } from "./helpers";
import RegisterSupporterForm from "./RegisterSupporterForm";

export default function Register({ campaign }) {
  const wardOptions = useWardOptions(campaign.id);
  return (<><PageTitle title="Register a supporter" sub="Quick capture in the field." /><RegisterSupporterForm campaignId={campaign.id} wardOptions={wardOptions} byCentre={campaign.operational_grain === "centre"} /></>);
}
