// Shared pure helpers for annual vs. monthly subscription pricing --
// formula: annual_price = monthly_price * 12 * (1 - reduction_annuelle).

function sanitizeMonthlyPrice(monthlyPrice) {
    const value = Number(monthlyPrice);
    return Number.isFinite(value) ? value : 0;
}

function sanitizeDiscountRate(discountRate) {
    const value = Number(discountRate);
    if (!Number.isFinite(value)) return 0;
    return Math.min(1, Math.max(0, value));
}

function round2(value) {
    return Math.round(value * 100) / 100;
}

export function computeAnnualPrice(monthlyPrice, discountRate) {
    const price = sanitizeMonthlyPrice(monthlyPrice);
    const rate = sanitizeDiscountRate(discountRate);
    return round2(price * 12 * (1 - rate));
}

export function annualSavingsAmount(monthlyPrice, discountRate) {
    const price = sanitizeMonthlyPrice(monthlyPrice);
    return round2(price * 12 - computeAnnualPrice(price, discountRate));
}
