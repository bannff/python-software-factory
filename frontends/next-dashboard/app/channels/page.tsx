"use client";
import { ChannelsPage } from "@/components/operations/channels/channels-page";

// Row 31 (feature-map) — /channels. Mounts the composed Channels surface with
// the deferred (empty) rooms data source until the channels backend lands.
export default function Page() {
  return <ChannelsPage channels={[]} />;
}
