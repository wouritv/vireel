import { describe, expect, it } from 'vitest';
import { BUILTIN_CAPTION_THEMES, findBuiltinCaptionTheme } from '../captionThemes';
import { ANIMATION_OPTIONS, FONT_OPTIONS } from '../subtitleOptions';

const HEX_COLOR = /^#[0-9A-F]{6}$/i;
const VALID_ANIMATIONS = new Set(ANIMATION_OPTIONS.map((a) => a.value));
const VALID_FONTS = new Set(FONT_OPTIONS.map((f) => f.value));
const VALID_TEXT_CASES = new Set(['none', 'uppercase', 'lowercase']);

describe('captionThemes', () => {
    it('has at least the built-in catalog size and unique ids/names/emojis', () => {
        expect(BUILTIN_CAPTION_THEMES.length).toBeGreaterThanOrEqual(30);

        const ids = BUILTIN_CAPTION_THEMES.map((t) => t.id);
        const names = BUILTIN_CAPTION_THEMES.map((t) => t.name);
        expect(new Set(ids).size).toBe(ids.length);
        expect(new Set(names).size).toBe(names.length);
    });

    it('gives every theme a non-empty id, name and emoji', () => {
        for (const theme of BUILTIN_CAPTION_THEMES) {
            expect(typeof theme.id).toBe('string');
            expect(theme.id.length).toBeGreaterThan(0);
            expect(typeof theme.name).toBe('string');
            expect(theme.name.length).toBeGreaterThan(0);
            expect(typeof theme.emoji).toBe('string');
            expect(theme.emoji.length).toBeGreaterThan(0);
        }
    });

    it('only references fonts and animations that actually exist in the picker', () => {
        for (const theme of BUILTIN_CAPTION_THEMES) {
            expect(VALID_FONTS.has(theme.style.fontFamily)).toBe(true);
            expect(VALID_ANIMATIONS.has(theme.style.animation)).toBe(true);
        }
    });

    it('gives every theme a fully-formed, sane style object', () => {
        for (const theme of BUILTIN_CAPTION_THEMES) {
            const style = theme.style;

            expect(style.positionX).toBeGreaterThanOrEqual(0);
            expect(style.positionX).toBeLessThanOrEqual(100);
            expect(style.positionY).toBeGreaterThanOrEqual(0);
            expect(style.positionY).toBeLessThanOrEqual(100);

            expect(style.fontSize).toBeGreaterThan(0);
            expect(style.borderWidth).toBeGreaterThanOrEqual(0);
            expect(style.shadowBlur).toBeGreaterThanOrEqual(0);
            expect(style.bgOpacity).toBeGreaterThanOrEqual(0);
            expect(style.bgOpacity).toBeLessThanOrEqual(1);
            expect(style.wordsPerLine).toBeGreaterThan(0);

            expect(style.fontColor).toMatch(HEX_COLOR);
            expect(style.highlightColor).toMatch(HEX_COLOR);
            expect(style.borderColor).toMatch(HEX_COLOR);
            expect(style.textShadowColor).toMatch(HEX_COLOR);
            expect(style.bgColor).toMatch(HEX_COLOR);

            expect(VALID_TEXT_CASES.has(style.textCase)).toBe(true);
            expect(typeof style.bold).toBe('boolean');
            expect(typeof style.italic).toBe('boolean');
        }
    });

    it('finds a theme by id and returns null for an unknown one', () => {
        const first = BUILTIN_CAPTION_THEMES[0];
        expect(findBuiltinCaptionTheme(first.id)).toBe(first);
        expect(findBuiltinCaptionTheme('does-not-exist')).toBeNull();
    });
});
