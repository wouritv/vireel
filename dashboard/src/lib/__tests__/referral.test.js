import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import {
    associateReferralCode,
    clearStoredReferralCode,
    getStoredReferralCode,
    looksLikeFreshSignup,
    storeReferralCode,
} from '../referral';
import { setCachedAccessToken } from '../apiAuth';

beforeEach(() => {
    localStorage.clear();
    setCachedAccessToken(null);
});

describe('storeReferralCode / getStoredReferralCode / clearStoredReferralCode', () => {
    it('round-trips a stored code', () => {
        storeReferralCode('ABC1234');
        expect(getStoredReferralCode()).toBe('ABC1234');
    });

    it('returns null when nothing is stored', () => {
        expect(getStoredReferralCode()).toBeNull();
    });

    it('clears the stored code', () => {
        storeReferralCode('ABC1234');
        clearStoredReferralCode();
        expect(getStoredReferralCode()).toBeNull();
    });

    it('ignores an empty/missing code', () => {
        storeReferralCode('');
        storeReferralCode(undefined);
        expect(getStoredReferralCode()).toBeNull();
    });
});

describe('looksLikeFreshSignup', () => {
    it('is true when created_at and last_sign_in_at are within 2 minutes', () => {
        const user = {
            created_at: '2026-01-01T00:00:00.000Z',
            last_sign_in_at: '2026-01-01T00:01:30.000Z',
        };
        expect(looksLikeFreshSignup(user)).toBe(true);
    });

    it('is false when they are far apart (returning user)', () => {
        const user = {
            created_at: '2026-01-01T00:00:00.000Z',
            last_sign_in_at: '2026-02-01T00:00:00.000Z',
        };
        expect(looksLikeFreshSignup(user)).toBe(false);
    });

    it('is false and never throws when fields are missing', () => {
        expect(looksLikeFreshSignup(undefined)).toBe(false);
        expect(looksLikeFreshSignup({})).toBe(false);
        expect(looksLikeFreshSignup(null)).toBe(false);
    });

    it('is false and never throws when fields are unparseable', () => {
        expect(looksLikeFreshSignup({ created_at: 'nope', last_sign_in_at: 'nope' })).toBe(false);
    });
});

describe('associateReferralCode', () => {
    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('returns null without calling fetch when code is empty', async () => {
        const fetchMock = vi.fn();
        vi.stubGlobal('fetch', fetchMock);
        const result = await associateReferralCode('user-1', '');
        expect(result).toBeNull();
        expect(fetchMock).not.toHaveBeenCalled();
    });

    it('returns the parsed JSON on success and clears the stored code', async () => {
        storeReferralCode('ABC1234');
        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ associated: true, signup_bonus_credits: 50 }),
        });
        vi.stubGlobal('fetch', fetchMock);

        const result = await associateReferralCode('user-1', 'ABC1234');

        expect(result).toEqual({ associated: true, signup_bonus_credits: 50 });
        expect(getStoredReferralCode()).toBeNull();
        expect(fetchMock).toHaveBeenCalledTimes(1);
        const [, options] = fetchMock.mock.calls[0];
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({ referral_code: 'ABC1234' });
    });

    it('returns null on an unknown/invalid code response (404) and clears the stored code', async () => {
        storeReferralCode('ABC1234');
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }));

        const result = await associateReferralCode('user-1', 'ABC1234');

        expect(result).toBeNull();
        expect(getStoredReferralCode()).toBeNull();
    });

    it('returns null on a bad-request response (400) and clears the stored code', async () => {
        storeReferralCode('ABC1234');
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 400, json: async () => ({}) }));

        const result = await associateReferralCode('user-1', 'ABC1234');

        expect(result).toBeNull();
        expect(getStoredReferralCode()).toBeNull();
    });

    it('returns null on a 401 (no session yet) but keeps the stored code for a later retry', async () => {
        storeReferralCode('ABC1234');
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) }));

        const result = await associateReferralCode('user-1', 'ABC1234');

        expect(result).toBeNull();
        expect(getStoredReferralCode()).toBe('ABC1234');
    });

    it('returns null on a network error but keeps the stored code for a later retry', async () => {
        storeReferralCode('ABC1234');
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));

        const result = await associateReferralCode('user-1', 'ABC1234');

        expect(result).toBeNull();
        expect(getStoredReferralCode()).toBe('ABC1234');
    });
});
