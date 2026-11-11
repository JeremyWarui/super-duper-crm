import { useMobilizers } from "../../api/hooks";
import { isLead, unitOf, useUnits, useWardOptions } from "./helpers";
import MobilizerForm from "./MobilizerForm";
import ManagerForm from "./ManagerForm";
import StaffForm from "./StaffForm";
import AreaPicker from "./AreaPicker";
import AssignMobilizerForm from "./AssignMobilizerForm";
import ScheduleEventForm from "./ScheduleEventForm";
import RecordForm from "./RecordForm";
import InviteForm from "./InviteForm";
import QrModal from "./QrModal";
import CampaignLinkModal from "./CampaignLinkModal";
import SchedulePaymentForm from "./SchedulePaymentForm";
import MarkPaidForm from "./MarkPaidForm";
import DeclinePaymentForm from "./DeclinePaymentForm";
import AssignForm from "./AssignForm";
import ReleaseForm from "./ReleaseForm";
import NotSentForm from "./NotSentForm";

// The form a page asked for with onModal; nothing when none is open.
export default function CampaignModal({ modal, campaign, role, onClose }) {
  const campaignId = campaign.id;
  const units = useUnits(campaignId);
  const wardOptions = useWardOptions(campaignId);
  const mobilizers = useMobilizers(campaignId);
  const { byCentre } = unitOf(campaign);
  return (
    <>
      {modal?.type === "mobilizer" && <MobilizerForm campaignId={campaignId} units={units} byCentre={byCentre} mobilizers={mobilizers.data || []} mobilizer={modal.mobilizer} onClose={onClose} />}
      {modal?.type === "manager" && <ManagerForm campaignId={campaignId} sitting={modal.sitting} onClose={onClose} />}
      {modal?.type === "staff" && <StaffForm campaignId={campaignId} role={modal.role} onClose={onClose} />}
      {modal?.type === "area" && <AreaPicker campaign={campaign} person={modal.person} onClose={onClose} />}
      {modal?.type === "assign" && <AssignMobilizerForm unit={modal.unit} holder={modal.holder} mobilizers={mobilizers.data || []} onClose={onClose} />}
      {modal?.type === "event" && <ScheduleEventForm campaignId={campaignId} wardOptions={wardOptions} byCentre={byCentre} onClose={onClose} />}
      {modal?.type === "record" && <RecordForm event={modal.event} onClose={onClose} />}
      {modal?.type === "invite" && <InviteForm event={modal.event} onClose={onClose} />}
      {modal?.type === "payment-schedule" && <SchedulePaymentForm campaignId={campaignId} role={role} onClose={onClose} />}
      {modal?.type === "payment-paid" && <MarkPaidForm payment={modal.payment} onClose={onClose} />}
      {modal?.type === "payment-decline" && <DeclinePaymentForm payment={modal.payment} onClose={onClose} />}
      {modal?.type === "assign-work" && <AssignForm campaignId={campaignId} event={modal.event} member={modal.member} onClose={onClose} />}
      {modal?.type === "payment-release" && <ReleaseForm payments={modal.payments} onClose={onClose} />}
      {modal?.type === "payment-notsent" && <NotSentForm payment={modal.payment} onClose={onClose} />}
      {modal?.type === "link" && <CampaignLinkModal campaign={campaign} onClose={onClose} />}
      {modal?.type === "qr" && <QrModal event={modal.event} canClose={isLead(role)} onClose={onClose} />}
    </>
  );
}
