import { describe, expect, it } from 'vitest';
import {
    findOverlappingVisual,
    validateVisualImageFile,
    validateVisualTiming,
    visualsOverlap,
} from '../reelVisuals';

describe('visualsOverlap', () => {
    it('is true when two ranges intersect', () => {
        expect(visualsOverlap({ start_time: 0, duration: 5 }, { start_time: 3, duration: 5 })).toBe(true);
    });

    it('is false when one range ends exactly where the other starts', () => {
        expect(visualsOverlap({ start_time: 0, duration: 5 }, { start_time: 5, duration: 5 })).toBe(false);
    });

    it('is false when the ranges are fully apart', () => {
        expect(visualsOverlap({ start_time: 0, duration: 2 }, { start_time: 10, duration: 2 })).toBe(false);
    });

    it('is true when one range fully contains the other', () => {
        expect(visualsOverlap({ start_time: 0, duration: 10 }, { start_time: 2, duration: 1 })).toBe(true);
    });

    it('treats a missing/invalid start_time or duration as 0 (a zero-length range never overlaps)', () => {
        expect(visualsOverlap({}, { start_time: 0, duration: 1 })).toBe(false);
        expect(visualsOverlap({ start_time: 1, duration: 1 }, {})).toBe(false);
    });
});

describe('findOverlappingVisual', () => {
    const existing = [
        { id: 'a', start_time: 0, duration: 5 },
        { id: 'b', start_time: 10, duration: 5 },
    ];

    it('returns the first overlapping visual', () => {
        expect(findOverlappingVisual({ start_time: 2, duration: 1 }, existing)).toBe(existing[0]);
    });

    it('returns null when nothing overlaps', () => {
        expect(findOverlappingVisual({ start_time: 6, duration: 2 }, existing)).toBeNull();
    });

    it('skips the excluded id (editing in place)', () => {
        expect(findOverlappingVisual({ start_time: 0, duration: 5 }, existing, 'a')).toBeNull();
    });

    it('treats a missing/non-array existingVisuals as no overlap', () => {
        expect(findOverlappingVisual({ start_time: 0, duration: 5 }, null)).toBeNull();
        expect(findOverlappingVisual({ start_time: 0, duration: 5 }, undefined)).toBeNull();
    });
});

describe('validateVisualTiming', () => {
    it('is valid when within bounds and non-overlapping', () => {
        expect(validateVisualTiming({ start_time: 1, duration: 2 }, 30, [])).toEqual({ valid: true });
    });

    it('rejects a negative start_time', () => {
        expect(validateVisualTiming({ start_time: -1, duration: 2 }, 30, [])).toEqual({
            valid: false,
            error: 'invalid_visual_timing',
        });
    });

    it('rejects a zero or negative duration', () => {
        expect(validateVisualTiming({ start_time: 0, duration: 0 }, 30, [])).toEqual({
            valid: false,
            error: 'invalid_visual_timing',
        });
        expect(validateVisualTiming({ start_time: 0, duration: -3 }, 30, [])).toEqual({
            valid: false,
            error: 'invalid_visual_timing',
        });
    });

    it('rejects start_time + duration exceeding the reel duration', () => {
        expect(validateVisualTiming({ start_time: 25, duration: 10 }, 30, [])).toEqual({
            valid: false,
            error: 'visual_exceeds_reel_duration',
        });
    });

    it('allows start_time + duration exactly equal to the reel duration', () => {
        expect(validateVisualTiming({ start_time: 25, duration: 5 }, 30, [])).toEqual({ valid: true });
    });

    it('rejects an overlap with an existing visual', () => {
        const existing = [{ id: 'a', start_time: 0, duration: 5 }];
        expect(validateVisualTiming({ start_time: 2, duration: 2 }, 30, existing)).toEqual({
            valid: false,
            error: 'visual_overlap',
        });
    });

    it('allows editing a visual in place without flagging it as overlapping itself', () => {
        const existing = [{ id: 'a', start_time: 0, duration: 5 }];
        expect(validateVisualTiming({ start_time: 1, duration: 5 }, 30, existing, 'a')).toEqual({ valid: true });
    });

    it('ignores a missing/non-finite reel duration (no upper bound check)', () => {
        expect(validateVisualTiming({ start_time: 0, duration: 5 }, null, [])).toEqual({ valid: true });
        expect(validateVisualTiming({ start_time: 0, duration: 5 }, undefined, [])).toEqual({ valid: true });
        expect(validateVisualTiming({ start_time: 0, duration: 5 }, NaN, [])).toEqual({ valid: true });
    });
});

describe('validateVisualImageFile', () => {
    it('accepts JPG, PNG and WebP under the size cap', () => {
        expect(validateVisualImageFile({ type: 'image/jpeg', size: 1024 })).toEqual({ valid: true });
        expect(validateVisualImageFile({ type: 'image/png', size: 1024 })).toEqual({ valid: true });
        expect(validateVisualImageFile({ type: 'image/webp', size: 1024 })).toEqual({ valid: true });
    });

    it('rejects a missing file', () => {
        expect(validateVisualImageFile(null)).toEqual({ valid: false, error: 'missing_file' });
        expect(validateVisualImageFile(undefined)).toEqual({ valid: false, error: 'missing_file' });
    });

    it('rejects an unsupported type', () => {
        expect(validateVisualImageFile({ type: 'image/gif', size: 1024 })).toEqual({
            valid: false,
            error: 'invalid_image_format',
        });
        expect(validateVisualImageFile({ type: 'application/pdf', size: 1024 })).toEqual({
            valid: false,
            error: 'invalid_image_format',
        });
    });

    it('rejects a file over the max size', () => {
        expect(validateVisualImageFile({ type: 'image/png', size: 9 * 1024 * 1024 })).toEqual({
            valid: false,
            error: 'image_too_large',
        });
    });

    it('is case-insensitive on the mime type', () => {
        expect(validateVisualImageFile({ type: 'IMAGE/JPEG', size: 1024 })).toEqual({ valid: true });
    });
});
