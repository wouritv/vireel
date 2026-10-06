import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { storeReferralCode } from "../lib/referral";

/**
 * Catches the "?ref=CODE" variant of a referral link (e.g. someone landing
 * directly on /login?ref=ABC1234) on any route change, independent of the
 * dedicated /r/:code landing page.
 */
export default function ReferralCapture() {
    const location = useLocation();

    useEffect(() => {
        const code = new URLSearchParams(location.search).get("ref");
        if (code) storeReferralCode(code);
    }, [location.search]);

    return null;
}
