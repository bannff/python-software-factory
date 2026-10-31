/** Shared types for all component renderers. */

export type ReactAdapterNode = {
  id: string;
  component: string;
  originalType: string;
  props: Record<string, unknown>;
  children?: ReactAdapterNode[];
  animation?: { effect: string; library: string };
};

export type RendererProps = {
  node: ReactAdapterNode;
  renderChildren: (children?: ReactAdapterNode[]) => React.ReactNode;
};
