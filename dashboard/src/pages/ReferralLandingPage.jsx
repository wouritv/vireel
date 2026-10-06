import { Navigate, useParams } from "react-router-dom";
import { storeReferralCode } from "../lib/referral";

/**
 * Public landing hit from a shared referral link (https://vireel.co/r/ABC1234).
 * Captures the code for later association (see lib/referral.js), then sends
 * the visitor straight into signup -- the code itself is never shown here.
 */
export default function ReferralLandingPage() {
    const { code } = useParams();
    storeReferralCode(code);
    return <Navigate to="/login?mode=signup" replace />;
}
