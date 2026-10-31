import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export async function listOwnerSecretNames(): Promise<string[]> {
  const data = unwrapToolData(await callTool("storage.owner_secret_list")) as { names?: unknown };
  if (!Array.isArray(data?.names) || !data.names.every((name) => typeof name === "string")) {
    throw new Error("Secret names unavailable.");
  }
  return data.names as string[];
}

export async function setOwnerSecret(name: string, value: string): Promise<void> {
  const data = unwrapToolData(await callTool("storage.owner_secret_set", { name, value })) as
    { ok?: unknown };
  if (data?.ok !== true) throw new Error("Secret could not be saved.");
}

export async function deleteOwnerSecret(name: string): Promise<boolean> {
  const data = unwrapToolData(await callTool("storage.owner_secret_delete", { name })) as
    { ok?: unknown };
  return data?.ok === true;
}
