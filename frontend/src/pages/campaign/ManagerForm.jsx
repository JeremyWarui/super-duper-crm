import { FormActions, InviteModal, Modal } from "../../components/ui";
import { useSetManager } from "../../api/hooks";
import { Btn, PrimaryBtn } from "./controls";
import LoginFields, { useLoginFields } from "./LoginFields";

// The aspirant adds the manager, or replaces `sitting`, whose login is then turned off.
export default function ManagerForm({ campaignId, sitting, onClose }) {
  const set = useSetManager();
  const fields = useLoginFields();
  const made = set.data;

  if (made) {
    return (
      <InviteModal title="Manager added" invite={made.invite} username={made.username} onClose={onClose}>
        {made.replaced && <>{made.replaced} is off the campaign and can no longer sign in.</>}
      </InviteModal>
    );
  }

  const save = () => set.mutate({ campaign: campaignId, ...fields.body, replace: !!sitting });
  return (
    <Modal title={sitting ? "Replace manager" : "Add manager"} sub={sitting ? `${sitting.full_name || sitting.username} comes off the campaign and their login is turned off.` : "One manager per campaign. They add mobilizers and run the day-to-day."} onClose={onClose}>
      <LoginFields form={fields.form} set={fields.set} />
      {set.error && <div className="form-error">{set.error.message}</div>}
      <FormActions>
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!fields.ok || set.isPending} onClick={save}>{set.isPending ? "Saving…" : sitting ? "Replace manager" : "Add manager"}</PrimaryBtn>
      </FormActions>
    </Modal>
  );
}
