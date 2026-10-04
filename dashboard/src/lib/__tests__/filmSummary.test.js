import { describe, expect, it, vi } from 'vitest';
import {
    buildFilmSummaryProcessSteps,
    errorMessageForCode,
    formatMsClock,
    isFilmSummaryRejectionErrorCode,
    narrationSceneOverlapScore,
    normalizeFilmSummaryJobStatus,
    rankSceneSuggestionsForSegment,
    usedClipSignaturesExcluding,
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

describe('usedClipSignaturesExcluding', () => {
    const segments = [
        { id: 'seg_001', clips: [{ scene_id: 'scene_001', start_ms: 0, end_ms: 1000 }] },
        { id: 'seg_002', clips: [{ scene_id: 'scene_002', start_ms: 2000, end_ms: 3000 }] },
    ];

    it('collects clip signatures from every segment except the excluded one', () => {
        const used = usedClipSignaturesExcluding(segments, 'seg_001');
        expect(used.has('scene_002|2000|3000')).toBe(true);
        expect(used.has('scene_001|0|1000')).toBe(false);
    });

    it('returns an empty set when segments is empty or missing', () => {
        expect(usedClipSignaturesExcluding([], 'seg_001').size).toBe(0);
        expect(usedClipSignaturesExcluding(undefined, 'seg_001').size).toBe(0);
    });
});

describe('narrationSceneOverlapScore', () => {
    it('scores higher when significant words are shared', () => {
        const score = narrationSceneOverlapScore(
            'Marie decouvre la verite sur son pere.',
            'Marie hurle: tu m\'as menti sur pere pendant toutes ces annees.'
        );
        expect(score).toBeGreaterThan(0);
    });

    it('returns zero when there is no shared vocabulary', () => {
        const score = narrationSceneOverlapScore('Marie decouvre la verite.', 'Le chat dort sur le canape.');
        expect(score).toBe(0);
    });

    it('returns zero when either text is empty', () => {
        expect(narrationSceneOverlapScore('', 'some text here')).toBe(0);
        expect(narrationSceneOverlapScore('some text here', '')).toBe(0);
        expect(narrationSceneOverlapScore(undefined, undefined)).toBe(0);
    });

    it('ignores accents and case when matching words', () => {
        const score = narrationSceneOverlapScore('La VERITE eclate enfin.', 'la verite finit par eclater.');
        expect(score).toBeGreaterThan(0);
    });
});

describe('rankSceneSuggestionsForSegment', () => {
    const sceneIndex = [
        { scene_id: 'scene_current', start_ms: 0, end_ms: 5000, speakers: ['A'], transcript_overlap: '' },
        { scene_id: 'scene_relevant', start_ms: 6000, end_ms: 9000, speakers: ['A'], transcript_overlap: 'Marie decouvre la verite sur son pere caches depuis toujours.' },
        { scene_id: 'scene_unrelated', start_ms: 500000, end_ms: 503000, speakers: ['B'], transcript_overlap: 'Le chat dort tranquillement sur le canape.' },
        { scene_id: 'scene_flagged', start_ms: 7000, end_ms: 8000, speakers: ['A'], transcript_overlap: '', quality_flags: ['blurred'] },
    ];
    const segment = {
        id: 'seg_001',
        narration: 'Marie decouvre enfin la verite sur son pere.',
        clips: [{ scene_id: 'scene_current', start_ms: 0, end_ms: 5000 }],
    };

    it('excludes scenes already used by this same segment', () => {
        const ranked = rankSceneSuggestionsForSegment({ segment, sceneIndex, allSegments: [segment] });
        expect(ranked.find((s) => s.scene_id === 'scene_current')).toBeUndefined();
    });

    it('ranks a narratively/temporally relevant scene above an unrelated distant one', () => {
        const ranked = rankSceneSuggestionsForSegment({ segment, sceneIndex, allSegments: [segment] });
        const relevantIndex = ranked.findIndex((s) => s.scene_id === 'scene_relevant');
        const unrelatedIndex = ranked.findIndex((s) => s.scene_id === 'scene_unrelated');
        expect(relevantIndex).toBeLessThan(unrelatedIndex);
    });

    it('penalizes a scene flagged by scene detection relative to an identical unflagged one', () => {
        const unflaggedTwin = { ...sceneIndex[3], scene_id: 'scene_unflagged_twin', quality_flags: [] };
        const ranked = rankSceneSuggestionsForSegment({
            segment, sceneIndex: [...sceneIndex, unflaggedTwin], allSegments: [segment],
        });
        const flagged = ranked.find((s) => s.scene_id === 'scene_flagged');
        const twin = ranked.find((s) => s.scene_id === 'scene_unflagged_twin');
        expect(flagged.score).toBeLessThan(twin.score);
    });

    it('flags a scene already used by another segment without excluding it', () => {
        const otherSegment = { id: 'seg_002', clips: [{ scene_id: 'scene_relevant', start_ms: 6000, end_ms: 9000 }] };
        const ranked = rankSceneSuggestionsForSegment({ segment, sceneIndex, allSegments: [segment, otherSegment] });
        const relevant = ranked.find((s) => s.scene_id === 'scene_relevant');
        expect(relevant).toBeDefined();
        expect(relevant.alreadyUsedElsewhere).toBe(true);
    });

    it('returns an empty list when sceneIndex is empty', () => {
        expect(rankSceneSuggestionsForSegment({ segment, sceneIndex: [], allSegments: [segment] })).toEqual([]);
    });
});
