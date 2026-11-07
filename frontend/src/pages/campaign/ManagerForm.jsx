import { useSetManager } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { InviteDialog } from "@/components/ui/invite-dialog";
import LoginFields, { useLoginFields } from "./LoginFields";

// The aspirant adds the manager, or replaces `sitting`, whose login is then turned off.
export default function ManagerForm({ campaignId, sitting, onClose }) {
  const set = useSetManager();
  const fields = useLoginFields();
  const made = set.data;

  if (made) {
    return (
      <InviteDialog title="Manager added" invite={made.invite} username={made.username} onClose={onClose}>
        {made.replaced && <>{made.replaced} is off the campaign and can no longer sign in.</>}
      </InviteDialog>
    );
  }

  const save = () => set.mutate({ campaign: campaignId, ...fields.body, replace: !!sitting });
  return (
    <Dialog title={sitting ? "Replace manager" : "Add manager"} description={sitting ? `${sitting.full_name || sitting.username} comes off the campaign and their login is turned off.` : "One manager per campaign. They add mobilizers and run the day-to-day."} onClose={onClose}>
      <LoginFields form={fields.form} set={fields.set} />
      <ErrorText error={set.error} />
      <FormActions>
        <Button shape="rounded" variant="quiet" onClick={onClose}>Cancel</Button>
        <Button shape="rounded" disabled={!fields.ok || set.isPending} onClick={save}>{set.isPending ? "Saving…" : sitting ? "Replace manager" : "Add manager"}</Button>
      </FormActions>
    </Dialog>
  );
}
