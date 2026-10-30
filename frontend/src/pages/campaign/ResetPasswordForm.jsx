import { Modal, PasswordModal } from "../../components/ui";
import { useResetTeamPassword } from "../../api/hooks";
import { Btn, PrimaryBtn } from "./controls";

export default function ResetPasswordForm({ campaignId, person, onClose }) {
  const reset = useResetTeamPassword();
  const name = person.full_name || person.username;
  if (reset.data) {
    return (
      <PasswordModal title="New password" password={reset.data.password} onClose={onClose}>
        <b>{reset.data.username}</b> signs in with this from now on. Their old password no longer works.
      </PasswordModal>
    );
  }
  return (
    <Modal title={`Reset ${name}'s password`} sub="Their old password stops working and they are signed out." onClose={onClose}>
      {reset.error && <div className="form-error">{reset.error.message}</div>}
      <div className={`flex justify-end gap-2 ${reset.error ? "form-actions" : ""}`.trim()}>
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={reset.isPending} onClick={() => reset.mutate({ campaign: campaignId, user: person.id })}>{reset.isPending ? "Resetting…" : "Reset password"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

