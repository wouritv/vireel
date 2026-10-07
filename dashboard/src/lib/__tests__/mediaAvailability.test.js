import { describe, it, expect, vi, afterEach } from 'vitest';
import { describeMediaAvailability } from '../mediaAvailability';

const FIXED_TODAY = new Date('2026-08-01T12:00:00');

describe('describeMediaAvailability', () => {
    afterEach(() => {
        vi.useRealTimers();
    });

    it('returns the unknown variant for a null mediaStatus', () => {
        expect(describeMediaAvailability(null, null)).toEqual({
            variant: 'unknown', translationKey: null, params: {}, disabled: false,
        });
    });

    it('returns the unknown variant for an undefined mediaStatus', () => {
        expect(describeMediaAvailability(undefined, undefined)).toEqual({
            variant: 'unknown', translationKey: null, params: {}, disabled: false,
        });
    });

    it('returns the unknown variant when AVAILABLE but mediaExpiresAt is falsy', () => {
        expect(describeMediaAvailability('AVAILABLE', null)).toEqual({
            variant: 'unknown', translationKey: null, params: {}, disabled: false,
        });
        expect(describeMediaAvailability('AVAILABLE', '')).toEqual({
            variant: 'unknown', translationKey: null, params: {}, disabled: false,
        });
    });

    it('returns the unknown variant when AVAILABLE but mediaExpiresAt is unparseable', () => {
        expect(describeMediaAvailability('AVAILABLE', 'not-a-date')).toEqual({
            variant: 'unknown', translationKey: null, params: {}, disabled: false,
        });
    });

    it('returns expiringSoon when AVAILABLE and expiring in 3 days or fewer', () => {
        vi.useFakeTimers();
        vi.setSystemTime(FIXED_TODAY);

        const result = describeMediaAvailability('AVAILABLE', '2026-08-03T13:00:00');
        expect(result).toEqual({
            variant: 'expiringSoon',
            translationKey: 'media.expiresInDays',
            params: { days: 3 },
            disabled: false,
        });
    });

    it('returns expiringSoon at the boundary (days === 3)', () => {
        vi.useFakeTimers();
        vi.setSystemTime(FIXED_TODAY);

        const result = describeMediaAvailability('AVAILABLE', '2026-08-03T13:00:00');
        expect(result.variant).toBe('expiringSoon');
        expect(result.params.days).toBe(3);
    });

    it('returns available with a formatted French date when expiring more than 3 days out', () => {
        vi.useFakeTimers();
        vi.setSystemTime(FIXED_TODAY);

        const result = describeMediaAvailability('AVAILABLE', '2026-08-20T00:00:00');
        expect(result.variant).toBe('available');
        expect(result.translationKey).toBe('media.availableUntil');
        expect(result.disabled).toBe(false);
        expect(result.params.date).toBe(
            new Date('2026-08-20T00:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })
        );
    });

    it('returns expired and disabled for EXPIRED', () => {
        expect(describeMediaAvailability('EXPIRED', null)).toEqual({
            variant: 'expired', translationKey: 'media.expired', params: {}, disabled: true,
        });
    });

    it('returns expired and disabled for DELETED', () => {
        expect(describeMediaAvailability('DELETED', null)).toEqual({
            variant: 'expired', translationKey: 'media.expired', params: {}, disabled: true,
        });
    });

    it('returns expired and disabled for MISSING', () => {
        expect(describeMediaAvailability('MISSING', null)).toEqual({
            variant: 'expired', translationKey: 'media.expired', params: {}, disabled: true,
        });
    });

    it('returns the unknown variant for an unrecognized status string', () => {
        expect(describeMediaAvailability('SOME_OTHER_STATUS', null)).toEqual({
            variant: 'unknown', translationKey: null, params: {}, disabled: false,
        });
    });
});
