"use client";

import { useEffect, useState } from "react";

/** true khi media query khớp; theo dõi khi đổi kích thước (lần vẽ đầu trên máy chủ luôn là false). */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    const list = window.matchMedia(query);
    const update = () => setMatches(list.matches);
    const first = setTimeout(update, 0);
    list.addEventListener("change", update);
    return () => {
      clearTimeout(first);
      list.removeEventListener("change", update);
    };
  }, [query]);
  return matches;
}
