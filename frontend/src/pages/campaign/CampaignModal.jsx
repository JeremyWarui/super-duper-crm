import { useMobilizers } from "../../api/hooks";
import { useUnits, useWardOptions } from "./helpers";
import MobilizerForm from "./MobilizerForm";
import ManagerForm from "./ManagerForm";
import ResetPasswordForm from "./ResetPasswordForm";
import AssignMobilizerForm from "./AssignMobilizerForm";
import ScheduleEventForm from "./ScheduleEventForm";
import RecordForm from "./RecordForm";
import InviteForm from "./InviteForm";
import QrModal from "./QrModal";

// The form a page asked for with onModal; nothing when none is open.
export default function CampaignModal({ modal, campaign, role, onClose }) {
  const campaignId = campaign.id;
  const units = useUnits(campaignId);
  const wardOptions = useWardOptions(campaignId);
  const mobilizers = useMobilizers(campaignId);
  const byCentre = campaign.operational_grain === "centre";
  return (
    <>
      {modal?.type === "mobilizer" && <MobilizerForm campaignId={campaignId} units={units} byCentre={byCentre} mobilizers={mobilizers.data || []} mobilizer={modal.mobilizer} onClose={onClose} />}
      {modal?.type === "manager" && <ManagerForm campaignId={campaignId} sitting={modal.sitting} onClose={onClose} />}
      {modal?.type === "reset" && <ResetPasswordForm campaignId={campaignId} person={modal.person} onClose={onClose} />}
      {modal?.type === "assign" && <AssignMobilizerForm unit={modal.unit} holder={modal.holder} mobilizers={mobilizers.data || []} onClose={onClose} />}
      {modal?.type === "event" && <ScheduleEventForm campaignId={campaignId} wardOptions={wardOptions} byCentre={byCentre} onClose={onClose} />}
      {modal?.type === "record" && <RecordForm event={modal.event} onClose={onClose} />}
      {modal?.type === "invite" && <InviteForm event={modal.event} onClose={onClose} />}
      {modal?.type === "qr" && <QrModal event={modal.event} canClose={role === "manager"} onClose={onClose} />}
    </>
  );
}
