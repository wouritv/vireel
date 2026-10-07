// Shared pure helpers for annual vs. monthly subscription pricing --
// formula: annual_price = monthly_price * 12 * (1 - reduction_annuelle/100).

function sanitizeMonthlyPrice(monthlyPrice) {
    const value = Number(monthlyPrice);
    return Number.isFinite(value) ? value : 0;
}

export function normalizeAnnualDiscountPercent(discountPercent) {
    const value = Number(discountPercent);
    if (!Number.isFinite(value)) return 0;
    if (value > 0 && value < 1) return Math.min(100, Math.max(0, value * 100));
    return Math.min(100, Math.max(0, value));
}

function round2(value) {
    return Math.round(value * 100) / 100;
}

export function computeAnnualPrice(monthlyPrice, discountPercent) {
    const price = sanitizeMonthlyPrice(monthlyPrice);
    const percent = normalizeAnnualDiscountPercent(discountPercent);
    return round2(price * 12 * (1 - percent / 100));
}

export function annualSavingsAmount(monthlyPrice, discountPercent) {
    const price = sanitizeMonthlyPrice(monthlyPrice);
    return round2(price * 12 - computeAnnualPrice(price, discountPercent));
}
