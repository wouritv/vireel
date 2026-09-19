import { describe, expect, it, vi } from 'vitest';
import {
    buildFilmSummaryProcessSteps,
    errorMessageForCode,
    formatMsClock,
    isFilmSummaryRejectionErrorCode,
    normalizeFilmSummaryJobStatus,
} from '../filmSummary';

const identityT = (key, fallback) => fallback ?? key;

describe('normalizeFilmSummaryJobStatus', () => {
    it('maps backend statuses to the frontend canonical form', () => {
        expect(normalizeFilmSummaryJobStatus('completed')).toBe('complete');
        expect(normalizeFilmSummaryJobStatus('failed')).toBe('error');
        expect(normalizeFilmSummaryJobStatus('queued')).toBe('processing');
        expect(normalizeFilmSummaryJobStatus('processing')).toBe('processing');
    });

    it('defaults to idle when status is missing', () => {
        expect(normalizeFilmSummaryJobStatus(undefined)).toBe('idle');
        expect(normalizeFilmSummaryJobStatus('')).toBe('idle');
    });
});

describe('errorMessageForCode', () => {
    it('maps known backend error codes to their i18n key', () => {
        const t = vi.fn((key) => `translated:${key}`);

        expect(errorMessageForCode(t, 'NOT_A_FILM', 'fallback')).toBe('translated:filmSummary.errorNotAFilm');
        expect(errorMessageForCode(t, 'SOURCE_TOO_SHORT', 'fallback')).toBe('translated:filmSummary.errorSourceTooShort');
        expect(errorMessageForCode(t, 'TTS_FAILED', 'fallback')).toBe('translated:filmSummary.errorTtsFailed');
        expect(errorMessageForCode(t, 'PLAN_INVALID', 'fallback')).toBe('translated:filmSummary.errorPlanInvalid');
        expect(errorMessageForCode(t, 'INSUFFICIENT_CREDITS', 'fallback')).toBe('translated:filmSummary.errorInsufficientCredits');
        expect(errorMessageForCode(t, 'JOB_CANCELLED', 'fallback')).toBe('translated:filmSummary.errorJobCancelled');
    });

    it('returns the fallback untouched when no code is given', () => {
        const t = vi.fn();
        expect(errorMessageForCode(t, '', 'fallback text')).toBe('fallback text');
        expect(errorMessageForCode(t, null, 'fallback text')).toBe('fallback text');
        expect(t).not.toHaveBeenCalled();
    });
});

describe('isFilmSummaryRejectionErrorCode', () => {
    it('recognizes rejection codes', () => {
        expect(isFilmSummaryRejectionErrorCode('NOT_A_FILM')).toBe(true);
        expect(isFilmSummaryRejectionErrorCode('SOURCE_TOO_LONG')).toBe(true);
    });

    it('does not treat technical failures as rejections', () => {
        expect(isFilmSummaryRejectionErrorCode('TRANSCRIPTION_FAILED')).toBe(false);
        expect(isFilmSummaryRejectionErrorCode('RENDER_FAILED')).toBe(false);
        expect(isFilmSummaryRejectionErrorCode('')).toBe(false);
        expect(isFilmSummaryRejectionErrorCode(undefined)).toBe(false);
    });
});

describe('formatMsClock', () => {
    it('formats sub-hour durations as m:ss', () => {
        expect(formatMsClock(0)).toBe('0:00');
        expect(formatMsClock(5000)).toBe('0:05');
        expect(formatMsClock(65000)).toBe('1:05');
    });

    it('formats hour-plus durations as h:mm:ss', () => {
        expect(formatMsClock(3661000)).toBe('1:01:01');
    });

    it('clamps negative/invalid input to zero', () => {
        expect(formatMsClock(-500)).toBe('0:00');
        expect(formatMsClock(undefined)).toBe('0:00');
    });
});

describe('buildFilmSummaryProcessSteps (analysis phase)', () => {
    const stateOf = (steps, key) => steps.find((s) => s.key === key).state;

    it('marks uploading done and transcribing active before any stage is reported', () => {
        const steps = buildFilmSummaryProcessSteps({ status: 'processing', stage: '', t: identityT, phase: 'analysis' });
        expect(stateOf(steps, 'uploading')).toBe('done');
        expect(stateOf(steps, 'transcribing')).toBe('active');
        expect(stateOf(steps, 'planning')).toBe('pending');
    });

    it('marks earlier stages done and the current one active', () => {
        const steps = buildFilmSummaryProcessSteps({ status: 'processing', stage: 'planning', t: identityT, phase: 'analysis' });
        expect(stateOf(steps, 'transcribing')).toBe('done');
        expect(stateOf(steps, 'detecting_scenes')).toBe('done');
        expect(stateOf(steps, 'validating_film')).toBe('done');
        expect(stateOf(steps, 'planning')).toBe('active');
        expect(stateOf(steps, 'validating_plan')).toBe('pending');
    });

    it('marks every stage done once the job is complete', () => {
        const steps = buildFilmSummaryProcessSteps({ status: 'complete', stage: 'validating_plan', t: identityT, phase: 'analysis' });
        for (const step of steps) {
            expect(step.state).toBe('done');
        }
    });

    it('marks the in-flight stage as error on failure', () => {
        const steps = buildFilmSummaryProcessSteps({ status: 'error', stage: 'detecting_scenes', t: identityT, phase: 'analysis' });
        expect(stateOf(steps, 'transcribing')).toBe('done');
        expect(stateOf(steps, 'detecting_scenes')).toBe('error');
        expect(stateOf(steps, 'validating_film')).toBe('pending');
    });
});

describe('buildFilmSummaryProcessSteps (render phase)', () => {
    const stateOf = (steps, key) => steps.find((s) => s.key === key).state;

    it('infers the render phase from a render stage when phase is omitted', () => {
        const steps = buildFilmSummaryProcessSteps({ status: 'processing', stage: 'rendering_preview', t: identityT });
        expect(stateOf(steps, 'generating_voice')).toBe('done');
        expect(stateOf(steps, 'rendering_preview')).toBe('active');
        expect(stateOf(steps, 'rendering_final')).toBe('pending');
    });

    it('marks every stage done once rendering completes', () => {
        const steps = buildFilmSummaryProcessSteps({ status: 'complete', stage: 'rendering_final', t: identityT, phase: 'render' });
        for (const step of steps) {
            expect(step.state).toBe('done');
        }
    });
});
