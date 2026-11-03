import { useEffect, useRef, type MutableRefObject } from "react";

/** True while the component is mounted; guards state updates that follow an await. */
export function useMounted(): MutableRefObject<boolean> {
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  return mounted;
}
