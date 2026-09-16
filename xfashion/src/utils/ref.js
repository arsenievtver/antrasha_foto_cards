import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { recordVisit } from "../api.js";

const REF_KEY = "xfashion_ref";
const VISIT_SENT_KEY = "xfashion_ref_visit_sent";

export function getStoredRef() {
  try {
    return sessionStorage.getItem(REF_KEY) || "";
  } catch {
    return "";
  }
}

export function useAttribution() {
  const location = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const ref = params.get("ref");
    if (ref && ref.trim()) {
      try {
        sessionStorage.setItem(REF_KEY, ref.trim());
      } catch {
        /* ignore */
      }
    }
    const stored = getStoredRef();
    if (!stored) return;
    try {
      if (sessionStorage.getItem(VISIT_SENT_KEY) === stored) return;
    } catch {
      return;
    }
    recordVisit(stored).then((r) => {
      if (r?.recorded) {
        try {
          sessionStorage.setItem(VISIT_SENT_KEY, stored);
        } catch {
          /* ignore */
        }
      }
    });
  }, [location.search]);
}
