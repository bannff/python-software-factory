import type { DatasetInput } from "./datasets-api";

export type DatasetFormErrors = Partial<Record<keyof DatasetInput | "form", string>>;

const NAME = /^[a-z][a-z0-9_-]{1,63}$/;
const SCHEME = /^[a-z][a-z0-9+.-]*:/i;
const DIGEST = /^sha256:[0-9a-f]{64}$/;

/** Mirrors ml_register_dataset's rules so a bad form fails per field before the round trip. */
export function validateDatasetForm(form: DatasetInput): DatasetFormErrors {
  const errors: DatasetFormErrors = {};
  if (!NAME.test(form.name)) errors.name = "Use 2–64 lowercase letters, digits, hyphen or underscore, starting with a letter.";
  if (!SCHEME.test(form.uri.trim())) errors.uri = "Use a URI with a scheme, e.g. s3://bucket/data.jsonl.";
  if (!SCHEME.test(form.manifest_uri.trim())) errors.manifest_uri = "Use a URI with a scheme, e.g. s3://bucket/manifest.json.";
  if (!DIGEST.test(form.digest.trim())) errors.digest = "Use sha256: followed by the 64-character hex digest.";
  if (!form.view_name.trim()) errors.view_name = "Enter the view name.";
  if (!form.view_schema_version.trim()) errors.view_schema_version = "Enter the view schema version.";
  return errors;
}

/** Typed server refusals, keyed by the code `errorReason` surfaces. */
const SERVER: Readonly<Record<string, readonly [keyof DatasetFormErrors, string]>> = {
  dataset_exists: ["name", "A dataset with this name already exists."],
  dataset_invalid: ["name", "The server rejected this dataset name."],
  dataset_digest_mismatch: ["digest", "The digest does not match the dataset content."],
  dataset_revision_conflict: ["form", "This dataset changed elsewhere. Reload and try again."],
  dataset_not_found: ["form", "This dataset no longer exists."],
};

export function serverDatasetError(reason: string | undefined): DatasetFormErrors | undefined {
  const code = reason === undefined ? undefined : Object.keys(SERVER).find((c) => reason.includes(c));
  return code ? { [SERVER[code][0]]: SERVER[code][1] } : undefined;
}
