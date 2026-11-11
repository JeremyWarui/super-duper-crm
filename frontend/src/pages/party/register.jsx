// Pieces the party registers (Members, Volunteers, Aspirants) share: filters with paging and export,
// links that open a record or set the status, and the officer's moves with a reason.
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { FormActions } from "@/components/ui/form-actions";
import { FilterSelect, Input } from "@/components/ui/input";
import { PAGE_SIZE } from "./helpers";

/**
 * A register's filters and page. `initial` names every filter; a `where` filter is a place and is sent
 * as its county, constituency and ward. Changing a filter goes back to the first page.
 * `exportFile(query)` downloads the filtered list; a failure lands in `exportError`.
 */
export function useRegister(useList, initial, exportFile) {
  const [filters, setFilters] = useState(initial);
  const [offset, setOffset] = useState(0);
  const [exportError, setExportError] = useState("");
  const set = (key) => (value) => { setFilters((f) => ({ ...f, [key]: value })); setOffset(0); };
  const { where, q, ...rest } = filters;
  const query = { ...rest, ...(q === undefined ? {} : { q: q.trim() }), ...where };
  const list = useList({ ...query, limit: PAGE_SIZE, offset });
  const exportCsv = async () => {
    setExportError("");
    try {
      await exportFile(query);
    } catch (e) {
      setExportError(e.message);
    }
  };
  return { filters, set, offset, setOffset, list, items: list.data?.items || [], total: list.data?.total ?? 0, exportCsv, exportError };
}

/** A link's `?open=<id>` (with a way to close it), and its `?status=` handed to `setStatus` each time it changes. */
export function useLinkedRecord(setStatus) {
  const [params, setParams] = useSearchParams();
  const wanted = params.get("status");
  const [applied, setApplied] = useState(null);
  if (wanted !== null && wanted !== applied) {
    setApplied(wanted);
    setStatus(wanted);
  }
  const close = () => setParams((p) => { p.delete("open"); return p; }, { replace: true });
  return { linked: params.get("open"), close };
}

/** A record opened from a link: `Detail` once `useRecord(id)` has loaded it. */
export function Linked({ id, useRecord, Detail, onClose }) {
  const record = useRecord(id);
  return record.data ? <Detail row={record.data} onClose={onClose} /> : null;
}

/** The status filter: every status in `labels`, after "All statuses". */
export const StatusFilter = ({ labels, value, onChange }) => (
  <FilterSelect label="Status" blank="All statuses" value={value} onChange={onChange} options={Object.entries(labels)} />
);

/** A reason box and one button per allowed move; `needsReason(status)` holds a move until a reason is typed. */
export function MoveButtons({ moves, move, id, placeholder, needsReason = () => false }) {
  const [reason, setReason] = useState("");
  if (!moves.length) return null;
  return (
    <>
      <Input aria-label="Reason" placeholder={placeholder} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
      <FormActions>
        {moves.map(([status, label]) => (
          <Button key={status + label} shape="rounded" variant={status === "approved" ? "primary" : "quiet"}
            disabled={move.isPending || (needsReason(status) && !reason.trim())}
            onClick={() => move.mutate({ id, status, reason: reason.trim() }, { onSuccess: () => setReason("") })}>
            {label}
          </Button>
        ))}
      </FormActions>
    </>
  );
}
