Design system notes

- Tokens are defined in `theme/static/css/_tokens.css` for runtime (loaded in `base_tailwind.html`) and in `theme/static_src/src/_tokens.css` for Tailwind build-time.
- Tailwind config extended in `theme/static_src/tailwind.config.js` with primary/accent colors and font family.
- Components: `templates/components/stat_card.html` is available for small stat cards. Create more components in `templates/components/` and reuse via `{% include %}`.

Build:
- From `theme/static_src/` run `npm run build` to regenerate `theme/static/css/dist/styles.css`.
