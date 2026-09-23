import { beforeEach, describe, expect, it, vi } from 'vitest';

const createClientMock = vi.fn();

vi.mock('@supabase/supabase-js', () => ({
    createClient: createClientMock,
}));

describe('getSupabaseBrowserClient', () => {
    beforeEach(() => {
        vi.resetModules();
        vi.clearAllMocks();
        vi.unstubAllEnvs();
        delete window.__ENV__;
    });

    it('prefers window.__ENV__ (runtime config) over the build-time env var', async () => {
        // window.__ENV__ is what the Docker entrypoint injects at container
        // startup (see dashboard/Dockerfile) so one built image can serve
        // demo and production against their own separate Supabase projects.
        vi.stubEnv('VITE_SUPABASE_URL', 'https://build-time.example.co');
        vi.stubEnv('VITE_SUPABASE_ANON_KEY', 'build-time-key');
        window.__ENV__ = {
            VITE_SUPABASE_URL: 'https://runtime.example.co',
            VITE_SUPABASE_ANON_KEY: 'runtime-key',
        };

        const fakeClient = { id: 'client-runtime' };
        createClientMock.mockReturnValue(fakeClient);

        const { getSupabaseBrowserClient } = await import('../supabase-browser');
        getSupabaseBrowserClient();

        expect(createClientMock).toHaveBeenCalledWith(
            'https://runtime.example.co',
            'runtime-key',
            expect.any(Object),
        );
    });

    it('falls back to the build-time env var when window.__ENV__ has no value', async () => {
        vi.stubEnv('VITE_SUPABASE_URL', 'https://build-time.example.co');
        vi.stubEnv('VITE_SUPABASE_ANON_KEY', 'build-time-key');
        window.__ENV__ = {};

        const fakeClient = { id: 'client-build-time' };
        createClientMock.mockReturnValue(fakeClient);

        const { getSupabaseBrowserClient } = await import('../supabase-browser');
        getSupabaseBrowserClient();

        expect(createClientMock).toHaveBeenCalledWith(
            'https://build-time.example.co',
            'build-time-key',
            expect.any(Object),
        );
    });

    it('throws when required env vars are missing', async () => {
        vi.stubEnv('VITE_SUPABASE_URL', '');
        vi.stubEnv('VITE_SUPABASE_ANON_KEY', '');

        const { getSupabaseBrowserClient } = await import('../supabase-browser');

        expect(() => getSupabaseBrowserClient()).toThrow(
            'Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY',
        );
    });

    it('creates and memoizes supabase client with expected auth options', async () => {
        vi.stubEnv('VITE_SUPABASE_URL', 'https://supabase.example.co');
        vi.stubEnv('VITE_SUPABASE_ANON_KEY', 'anon-key');

        const fakeClient = { id: 'client-1' };
        createClientMock.mockReturnValue(fakeClient);

        const { getSupabaseBrowserClient } = await import('../supabase-browser');

        const first = getSupabaseBrowserClient();
        const second = getSupabaseBrowserClient();

        expect(first).toBe(fakeClient);
        expect(second).toBe(fakeClient);
        expect(createClientMock).toHaveBeenCalledTimes(1);
        expect(createClientMock).toHaveBeenCalledWith(
            'https://supabase.example.co',
            'anon-key',
            {
                auth: {
                    persistSession: true,
                    autoRefreshToken: true,
                    detectSessionInUrl: true,
                },
            },
        );
    });
});

