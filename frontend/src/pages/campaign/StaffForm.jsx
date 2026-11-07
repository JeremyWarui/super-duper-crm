import { FormActions, InviteModal, Modal } from "../../components/ui";
import { useAddStaff } from "../../api/hooks";
import { Btn, PrimaryBtn } from "./controls";
import { ROLE_LABEL } from "./helpers";
import LoginFields, { useLoginFields } from "./LoginFields";

const SUB = {
  coordinator: "A coordinator works the wards you give them, and sees only those.",
  comms: "A comms officer runs events and the website.",
};

// Adds a coordinator or comms officer to the campaign.
export default function StaffForm({ campaignId, role, onClose }) {
  const add = useAddStaff();
  const fields = useLoginFields();
  const label = ROLE_LABEL[role];
  const made = add.data;

  if (made) {
    return (
      <InviteModal title={`${label} added`} invite={made.invite} username={made.username} onClose={onClose}>
        {role === "coordinator" && "Set their area next: until then they see no wards."}
      </InviteModal>
    );
  }

  return (
    <Modal title={`Add ${label.toLowerCase()}`} sub={SUB[role]} onClose={onClose}>
      <LoginFields form={fields.form} set={fields.set} />
      {add.error && <div className="form-error">{add.error.message}</div>}
      <FormActions>
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!fields.ok || add.isPending} onClick={() => add.mutate({ campaign: campaignId, role, ...fields.body })}>{add.isPending ? "Saving…" : `Add ${label.toLowerCase()}`}</PrimaryBtn>
      </FormActions>
    </Modal>
  );
}
