import { describe, expect, it } from 'vitest';
import { annualSavingsAmount, computeAnnualPrice } from '../billing';

describe('computeAnnualPrice', () => {
    it('applies the discount rate to 12 months of the monthly price', () => {
        expect(computeAnnualPrice(10, 0.05)).toBe(114);
    });

    it('returns exactly monthly*12 when the discount rate is 0', () => {
        expect(computeAnnualPrice(10, 0)).toBe(120);
    });

    it('treats a missing/null discount rate as 0', () => {
        expect(computeAnnualPrice(10, null)).toBe(120);
        expect(computeAnnualPrice(10, undefined)).toBe(120);
    });

    it('clamps a negative or >1 discount rate to [0, 1]', () => {
        expect(computeAnnualPrice(10, -0.5)).toBe(120);
        expect(computeAnnualPrice(10, 1.5)).toBe(0);
    });

    it('treats a missing/invalid monthly price as 0', () => {
        expect(computeAnnualPrice(null, 0.05)).toBe(0);
        expect(computeAnnualPrice(undefined, 0.05)).toBe(0);
        expect(computeAnnualPrice(NaN, 0.05)).toBe(0);
    });
});

describe('annualSavingsAmount', () => {
    it('is the difference between monthly*12 and the discounted annual price', () => {
        expect(annualSavingsAmount(10, 0.05)).toBe(6);
    });

    it('is 0 when the discount rate is 0', () => {
        expect(annualSavingsAmount(10, 0)).toBe(0);
    });

    it('treats a missing/null discount rate as 0', () => {
        expect(annualSavingsAmount(10, null)).toBe(0);
        expect(annualSavingsAmount(10, undefined)).toBe(0);
    });

    it('clamps a negative or >1 discount rate to [0, 1]', () => {
        expect(annualSavingsAmount(10, -0.5)).toBe(0);
        expect(annualSavingsAmount(10, 1.5)).toBe(120);
    });

    it('treats a missing/invalid monthly price as 0', () => {
        expect(annualSavingsAmount(null, 0.05)).toBe(0);
        expect(annualSavingsAmount(undefined, 0.05)).toBe(0);
        expect(annualSavingsAmount(NaN, 0.05)).toBe(0);
    });
});
