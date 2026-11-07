import { useAddStaff } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { InviteDialog } from "@/components/ui/invite-dialog";
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
      <InviteDialog title={`${label} added`} invite={made.invite} username={made.username} onClose={onClose}>
        {role === "coordinator" && "Set their area next: until then they see no wards."}
      </InviteDialog>
    );
  }

  return (
    <Dialog title={`Add ${label.toLowerCase()}`} description={SUB[role]} onClose={onClose}>
      <LoginFields form={fields.form} set={fields.set} />
      <ErrorText error={add.error} />
      <FormActions>
        <Button shape="rounded" variant="quiet" onClick={onClose}>Cancel</Button>
        <Button shape="rounded" disabled={!fields.ok || add.isPending} onClick={() => add.mutate({ campaign: campaignId, role, ...fields.body })}>{add.isPending ? "Saving…" : `Add ${label.toLowerCase()}`}</Button>
      </FormActions>
    </Dialog>
  );
}
