import type { JobInput } from "./finetune-api";

export type JobFormErrors = Partial<Record<keyof JobInput, string>>;

const REQUIRED: Record<keyof JobInput, string> = {
  method: "Pick a method.", base_model: "Enter the base model.", dataset_uri: "Enter the dataset URI.",
  manifest_uri: "Enter the manifest URI.", dataset_digest: "Enter the dataset digest.",
  view_name: "Enter the view name.", view_schema_version: "Enter the view schema version.",
};

const SCHEME = /^[a-z][a-z0-9+.-]*:/i;
const SHA256_HEX = /^[0-9a-f]{64}$/i;

/** Mirrors the tool's rules (all fields required, URIs need a scheme, digest is SHA-256 hex) so a bad form fails per field. */
export function validateJobForm(form: JobInput): JobFormErrors {
  const errors: JobFormErrors = {};
  for (const key of Object.keys(REQUIRED) as (keyof JobInput)[]) {
    if (!form[key].trim()) errors[key] = REQUIRED[key];
  }
  if (!errors.dataset_uri && !SCHEME.test(form.dataset_uri.trim())) errors.dataset_uri = "Use a URI with a scheme, e.g. s3://bucket/data.jsonl.";
  if (!errors.manifest_uri && !SCHEME.test(form.manifest_uri.trim())) errors.manifest_uri = "Use a URI with a scheme, e.g. s3://bucket/manifest.json.";
  if (!errors.dataset_digest && !SHA256_HEX.test(form.dataset_digest.trim())) errors.dataset_digest = "Use the 64-character SHA-256 hex digest, without a prefix.";
  return errors;
}
