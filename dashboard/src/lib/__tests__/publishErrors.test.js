import { describe, expect, it, vi } from 'vitest';
import { describePublishError } from '../publishErrors';

// Mirrors LanguageContext's real t(key, fallback, vars): substitutes
// {{var}} placeholders into the fallback text, the same way the app's
// translate function does when no dictionary entry overrides it.
const identityT = (key, fallback, vars = {}) => {
    if (typeof fallback !== 'string') return fallback;
    return fallback.replace(/\{\{\s*(\w+)\s*\}\}/g, (_match, k) =>
        Object.prototype.hasOwnProperty.call(vars, k) ? String(vars[k]) : ''
    );
};

describe('describePublishError', () => {
    it('formats a publish_quota_exceeded object into a friendly message with the max and reset time', () => {
        const detail = {
            code: 'publish_quota_exceeded',
            message: 'some backend string, not relied on',
            max_daily: 5,
            used_today: 5,
            resets_at: '2026-01-02T00:00:00+00:00',
        };

        const message = describePublishError(identityT, detail, 'fallback');

        expect(message).not.toBe(detail);
        expect(typeof message).toBe('string');
        expect(message).toContain('5');
        // Same formatting the util itself uses, so the test stays correct
        // regardless of the machine's timezone.
        const expectedTime = new Date(detail.resets_at).toLocaleTimeString('fr-FR', {
            hour: '2-digit',
            minute: '2-digit',
        });
        expect(message).toContain(expectedTime);
    });

    it('calls t with the quota key and the max/time vars', () => {
        const t = vi.fn((key, fallback) => fallback);
        const detail = {
            code: 'publish_quota_exceeded',
            max_daily: 3,
            used_today: 3,
            resets_at: '2026-01-02T00:00:00+00:00',
        };

        describePublishError(t, detail, 'fallback');

        expect(t).toHaveBeenCalledWith(
            'publishQuota.exceeded',
            expect.any(String),
            expect.objectContaining({ max: 3 })
        );
    });

    it('returns a plain string detail unchanged', () => {
        expect(describePublishError(identityT, 'No active subscription or valid credit', 'fallback')).toBe(
            'No active subscription or valid credit'
        );
    });

    it('falls back for null, undefined, and empty string details', () => {
        expect(describePublishError(identityT, null, 'fallback text')).toBe('fallback text');
        expect(describePublishError(identityT, undefined, 'fallback text')).toBe('fallback text');
        expect(describePublishError(identityT, '', 'fallback text')).toBe('fallback text');
    });

    it('falls back for an object detail that is not the quota shape', () => {
        expect(describePublishError(identityT, { code: 'some_other_error' }, 'fallback text')).toBe('fallback text');
    });

    it('uses the generic translated message when no fallback is given', () => {
        const t = vi.fn((key, fallback) => fallback ?? key);
        expect(describePublishError(t, null, undefined)).toBe('Une erreur est survenue.');
        expect(t).toHaveBeenCalledWith('publishQuota.genericError', expect.any(String));
    });
});
